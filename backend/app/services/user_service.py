"""Cadastro de usuários pela equipe técnica (ainda não há tela para isso): o primeiro NIT e os autores."""

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserRole
from app.models.limits import EMAIL_MAX_LENGTH
from app.services.auth_service import get_user_by_email

MIN_PASSWORD_LENGTH = 8
# O bcrypt só considera os primeiros 72 bytes da senha; mais que isso daria uma falsa sensação de segurança.
MAX_PASSWORD_BYTES = 72


class UserAlreadyExistsError(Exception):
    """Já existe um usuário com este e-mail."""


class InvalidUserDataError(ValueError):
    """E-mail ou senha fora das regras."""


def normalize_email(email: str) -> str:
    """Valida o formato e devolve o e-mail como o login procura: sem espaços nas pontas e em minúsculas."""
    value = email.strip().lower()
    if len(value) > EMAIL_MAX_LENGTH:
        raise InvalidUserDataError(f"O e-mail passa de {EMAIL_MAX_LENGTH} caracteres.")
    try:
        validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        raise InvalidUserDataError(f"E-mail inválido: {email.strip()!r}.") from None
    return value


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidUserDataError(f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")
    if not password.strip():
        raise InvalidUserDataError("A senha não pode ser só espaços.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise InvalidUserDataError(f"A senha passa de {MAX_PASSWORD_BYTES} bytes, o máximo aceito.")


def create_user(db: Session, email: str, password: str, role: UserRole) -> User:
    """Cria um usuário com a senha guardada como hash. Faz commit.

    Recusa e-mail já cadastrado (sem diferenciar maiúsculas) e senha fora das regras.
    """
    normalized = normalize_email(email)
    validate_password(password)
    if get_user_by_email(db, normalized) is not None:
        raise UserAlreadyExistsError(f"Já existe um usuário com o e-mail {normalized}.")

    user = User(email=normalized, hashed_password=hash_password(password), role=role)
    db.add(user)
    db.commit()
    return user
