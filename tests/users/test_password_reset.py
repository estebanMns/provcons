import asyncio
import json

import httpx
import pytest

from app.core.exceptions import ServiceUnavailableError, UnauthorizedError, ValidationError
from app.core.security import create_access_token, create_reset_token, decode_access_token
from app.infrastructure.email import EmailError, ResendEmailSender
from app.modules.users.models import User
from app.modules.users.password_reset import FORGOT_MESSAGE, PasswordResetService, RateLimiter


def _user(email="ana@obra.com", password="clave-vieja-1"):
    user = User(id=7, email=email, full_name="Ana Pérez", organization_id=3)
    user.set_password(password)
    return user


class FakeUsers:
    def __init__(self, *users):
        self.users = {u.id: u for u in users}
        self.saved = 0

    async def get_by_email_insensitive(self, email):
        return next((u for u in self.users.values() if u.email.lower() == email.strip().lower()), None)

    async def get_by_id(self, user_id):
        return self.users.get(user_id)

    async def save(self, user):
        self.saved += 1
        return user


class FakeAudit:
    def __init__(self):
        self.actions = []

    async def record(self, action, **kwargs):
        self.actions.append(action)


class FakeEmail:
    def __init__(self, error=None):
        self.sent, self.error = [], error

    async def send(self, to, subject, html, text):
        if self.error:
            raise self.error
        self.sent.append({"to": to, "subject": subject, "html": html, "text": text})


def _service(users, email=None, limiter=None):
    return PasswordResetService(users, FakeAudit(), email, limiter or RateLimiter())


def _token_from(sent):
    return sent["text"].split("token=")[1].split()[0]


def test_correo_registrado_recibe_el_enlace():
    email = FakeEmail()
    service = _service(FakeUsers(_user()), email)
    message = asyncio.run(service.request_reset("  ANA@obra.com "))

    assert message == FORGOT_MESSAGE
    [sent] = email.sent
    assert sent["to"] == "ana@obra.com"
    assert "/restablecer?token=" in sent["text"] and "/restablecer?token=" in sent["html"]
    assert "Ana Pérez" in sent["html"]
    assert service.audit.actions == ["user.password_reset_requested"]


def test_correo_no_registrado_da_la_misma_respuesta_sin_enviar_nada():
    email = FakeEmail()
    assert asyncio.run(_service(FakeUsers(_user()), email).request_reset("nadie@obra.com")) == FORGOT_MESSAGE
    assert email.sent == []


def test_el_enlace_cambia_la_contrasena_y_sirve_una_sola_vez():
    user, email = _user(), FakeEmail()
    users = FakeUsers(user)
    service = _service(users, email)
    asyncio.run(service.request_reset("ana@obra.com"))
    token = _token_from(email.sent[0])

    asyncio.run(service.reset(token, "clave-nueva-2"))
    assert user.verify_password("clave-nueva-2") and not user.verify_password("clave-vieja-1")
    assert service.audit.actions[-1] == "user.password_reset"

    with pytest.raises(ValidationError, match="ya se usó"):
        asyncio.run(service.reset(token, "otra-clave-3"))
    assert user.verify_password("clave-nueva-2")


def test_enlace_vencido_o_adulterado_no_sirve():
    user = _user()
    service = _service(FakeUsers(user), FakeEmail())
    vencido = create_reset_token(user.id, user.password_hash, minutes=-1)
    with pytest.raises(ValidationError, match="venció"):
        asyncio.run(service.reset(vencido, "clave-nueva-2"))
    with pytest.raises(ValidationError, match="no es válido"):
        asyncio.run(service.reset(vencido[:-4] + "abcd", "clave-nueva-2"))


def test_token_de_sesion_y_enlace_de_recuperacion_no_se_mezclan():
    user = _user()
    service = _service(FakeUsers(user), FakeEmail())
    with pytest.raises(ValidationError):
        asyncio.run(service.reset(create_access_token(user.id), "clave-nueva-2"))
    with pytest.raises(UnauthorizedError):
        decode_access_token(create_reset_token(user.id, user.password_hash))


def test_si_el_correo_falla_la_respuesta_no_cambia():
    service = _service(FakeUsers(_user()), FakeEmail(error=EmailError("Resend caído")))
    assert asyncio.run(service.request_reset("ana@obra.com")) == FORGOT_MESSAGE
    assert service.audit.actions == []


def test_sin_proveedor_de_correo_se_avisa_que_no_esta_configurado():
    with pytest.raises(ServiceUnavailableError):
        asyncio.run(_service(FakeUsers(_user()), email=None).request_reset("ana@obra.com"))


def test_maximo_tres_solicitudes_por_correo():
    email = FakeEmail()
    service = _service(FakeUsers(_user()), email, RateLimiter(max_requests=3, window_seconds=900))
    for _ in range(5):
        assert asyncio.run(service.request_reset("ana@obra.com")) == FORGOT_MESSAGE
    assert len(email.sent) == 3


def test_resend_recibe_la_peticion_correcta():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"] = str(request.url), request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "abc"})

    sender = ResendEmailSender("re_test", "ProvCons <onboarding@resend.dev>", transport=httpx.MockTransport(handler))
    asyncio.run(sender.send("ana@obra.com", "Asunto", "<p>hola</p>", "hola"))
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["auth"] == "Bearer re_test"
    assert seen["body"]["to"] == ["ana@obra.com"] and seen["body"]["from"].endswith("<onboarding@resend.dev>")


def test_resend_con_error_lanza_el_motivo():
    transport = httpx.MockTransport(lambda r: httpx.Response(403, json={"message": "solo puedes enviar a tu correo"}))
    with pytest.raises(EmailError, match="403"):
        asyncio.run(ResendEmailSender("re_test", "x@y.com", transport=transport).send("a@b.com", "s", "h", "t"))
