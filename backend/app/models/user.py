from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.columns import enum_column_type
from app.models.enums import UserRole
from app.models.limits import (
    EMAIL_MAX_LENGTH,
    PASSWORD_HASH_MAX_LENGTH,
    USER_ROLE_MAX_LENGTH,
)

if TYPE_CHECKING:
    from app.models.asset import Asset


class User(Base):
    """Usuário do sistema: membro da equipe do NIT ou autor/inventor."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(PASSWORD_HASH_MAX_LENGTH))
    role: Mapped[UserRole] = mapped_column(
        enum_column_type(UserRole, name="user_role", length=USER_ROLE_MAX_LENGTH),
        default=UserRole.AUTOR,
    )

    # Ativos em que este usuário está vinculado como autor com acesso de acompanhamento (US07).
    assets: Mapped[list[Asset]] = relationship(back_populates="author_user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
