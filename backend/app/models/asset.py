from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.columns import enum_column_type
from app.models.enums import AssetType
from app.models.limits import (
    ASSET_TYPE_MAX_LENGTH,
    AUTHORS_MAX_LENGTH,
    PROCESS_NUMBER_MAX_LENGTH,
    STATUS_MAX_LENGTH,
    TITLE_MAX_LENGTH,
)

if TYPE_CHECKING:
    from app.models.user import User


class Asset(Base):
    """Ativo de propriedade intelectual acompanhado junto ao INPI (US04)."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    asset_type: Mapped[AssetType] = mapped_column(
        enum_column_type(AssetType, name="asset_type", length=ASSET_TYPE_MAX_LENGTH)
    )
    # Número do processo no INPI (ex.: "BR 10 2023 001234-5"). É a chave usada
    # no cruzamento com os despachos da RPI (Step 3), por isso é único e indexado.
    process_number: Mapped[str] = mapped_column(String(PROCESS_NUMBER_MAX_LENGTH), unique=True, index=True)
    deposit_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(STATUS_MAX_LENGTH))
    # Nomes dos inventores/autores conforme o depósito, separados por vírgula.
    authors: Mapped[str] = mapped_column(String(AUTHORS_MAX_LENGTH))

    # Autor com acesso de acompanhamento ao processo (opcional — US07).
    # SET NULL: se o usuário for removido, o ativo continua cadastrado.
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None
    )
    author_user: Mapped[User | None] = relationship(back_populates="assets")

    @property
    def author_email(self) -> str | None:
        """E-mail do autor vinculado, exposto diretamente na resposta da API."""
        return self.author_user.email if self.author_user else None

    def __repr__(self) -> str:
        return f"<Asset id={self.id} process={self.process_number!r} type={self.asset_type.value}>"
