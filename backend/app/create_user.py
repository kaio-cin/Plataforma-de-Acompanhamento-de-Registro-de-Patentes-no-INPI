"""Cria um usuário do sistema (NIT ou AUTOR) pelo terminal.

Execute a partir da pasta backend:  python -m app.create_user --email nit@instituicao.edu.br --perfil NIT

A senha é pedida duas vezes e não aparece na tela. O comando usa o banco de DATABASE_URL: para criar
o usuário no banco publicado, rode no seu computador com DATABASE_URL apontando para o endereço externo
do banco (ver README, seção "Publicação").
"""

import argparse
import getpass
from collections.abc import Callable

from sqlalchemy.engine import make_url

from app.core.config import settings
from app.database import SessionLocal
from app.database.init_db import init_db
from app.models import UserRole
from app.services import user_service


def _database_label() -> str:
    """Banco em uso, sem a senha, para conferir antes de criar o usuário no lugar errado."""
    return make_url(settings.database_url).render_as_string(hide_password=True)


def main(argv: list[str] | None = None, read_password: Callable[[str], str] = getpass.getpass) -> None:
    parser = argparse.ArgumentParser(description="Cria um usuário do sistema (NIT ou AUTOR).")
    parser.add_argument("--email", required=True, help="e-mail usado no login")
    parser.add_argument(
        "--perfil",
        required=True,
        choices=[role.value for role in UserRole],
        help="NIT vê toda a carteira; AUTOR vê só os ativos vinculados a ele",
    )
    args = parser.parse_args(argv)

    print(f"Banco: {_database_label()}")
    password = read_password("Senha: ")
    if read_password("Repita a senha: ") != password:
        print("As senhas não conferem. Nenhum usuário foi criado.")
        raise SystemExit(1)

    init_db()
    with SessionLocal() as db:
        try:
            user = user_service.create_user(db, args.email, password, UserRole(args.perfil))
        except (user_service.UserAlreadyExistsError, user_service.InvalidUserDataError) as exc:
            print(f"{exc} Nenhum usuário foi criado.")
            raise SystemExit(1) from None
    print(f"Usuário criado: {user.email} ({user.role.value}).")


if __name__ == "__main__":
    main()
