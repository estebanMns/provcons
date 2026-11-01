"""Restablece la contraseña de un usuario directamente en la base de datos.

Para el administrador, cuando alguien no puede usar el enlace por correo:

    .\\.venv\\Scripts\\python.exe scripts\\reset_password.py correo@empresa.com

Pide la nueva contraseña dos veces sin mostrarla en pantalla. Usa la base de
datos del .env (la misma de la app).
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.audit import AuditRepository, AuditService  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.modules.users.repository import UserRepository  # noqa: E402

MIN_LENGTH, MAX_LENGTH = 8, 72  # las mismas reglas que el registro
engine.echo = False  # en desarrollo el engine imprime cada SQL; aquí solo estorba


def ask_password() -> str:
    while True:
        first = getpass.getpass("Nueva contraseña: ")
        if not MIN_LENGTH <= len(first) <= MAX_LENGTH:
            print(f"Debe tener entre {MIN_LENGTH} y {MAX_LENGTH} caracteres.")
            continue
        if getpass.getpass("Repítela: ") != first:
            print("No coinciden, intenta de nuevo.")
            continue
        return first


async def reset(email: str) -> int:
    try:
        async with AsyncSessionLocal() as db:
            repo = UserRepository(db)
            user = await repo.get_by_email_insensitive(email)
            if user is None:
                print(f"No existe ningún usuario con el correo {email}. No se cambió nada.")
                return 1

            print(f"Usuario: {user.full_name} <{user.email}>")
            user.set_password(ask_password())
            await repo.save(user)
            await AuditService(AuditRepository(db)).record(
                action="user.password_reset_admin", resource_type="User", resource_id=user.id,
                actor_organization_id=user.organization_id,
            )
            print("Listo: la contraseña se actualizó. Ya puedes ingresar con la nueva.")
            return 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Restablece la contraseña de un usuario de ProvCons.")
    parser.add_argument("email", help="correo del usuario")
    args = parser.parse_args()
    try:
        sys.exit(asyncio.run(reset(args.email)))
    except KeyboardInterrupt:
        print("\nCancelado. No se cambió nada.")
        sys.exit(130)


if __name__ == "__main__":
    main()
