"""Da (o quita) el permiso de administrador de ProvCons a un usuario.

El administrador de la app ve la pestaña Rendimiento. No es lo mismo que el
rol "admin" de cada empresa, que recibe quien la registra. Este permiso solo
se da desde aquí, nunca desde la web:

    .\\.venv\\Scripts\\python.exe scripts\\make_admin.py correo@empresa.com
    .\\.venv\\Scripts\\python.exe scripts\\make_admin.py correo@empresa.com --quitar

Usa la base de datos del .env (la misma de la app).
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.audit import AuditRepository, AuditService  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.modules.users.repository import UserRepository  # noqa: E402

engine.echo = False  # en desarrollo el engine imprime cada SQL; aquí solo estorba


async def set_admin(email: str, grant: bool) -> int:
    try:
        async with AsyncSessionLocal() as db:
            repo = UserRepository(db)
            user = await repo.get_by_email_insensitive(email)
            if user is None:
                print(f"No existe ningún usuario con el correo {email}. No se cambió nada.")
                return 1

            print(f"Usuario: {user.full_name} <{user.email}>")
            if bool(user.is_platform_admin) == grant:
                print("Ya estaba así. No se cambió nada.")
                return 0
            user.is_platform_admin = grant
            await repo.save(user)
            await AuditService(AuditRepository(db)).record(
                action="user.platform_admin_granted" if grant else "user.platform_admin_revoked",
                resource_type="User", resource_id=user.id, actor_organization_id=user.organization_id,
            )
            print("Listo: ahora es administrador de la app. Vuelve a cargar la página para ver Rendimiento."
                  if grant else "Listo: ya no es administrador de la app.")
            return 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Da o quita el permiso de administrador de ProvCons.")
    parser.add_argument("email", help="correo del usuario")
    parser.add_argument("--quitar", action="store_true", help="quita el permiso en lugar de darlo")
    args = parser.parse_args()
    sys.exit(asyncio.run(set_admin(args.email, grant=not args.quitar)))


if __name__ == "__main__":
    main()
