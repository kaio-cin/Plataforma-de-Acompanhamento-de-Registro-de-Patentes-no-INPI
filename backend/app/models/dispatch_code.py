from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.columns import enum_column_type
from app.models.enums import AssetType
from app.models.limits import (
    ASSET_TYPE_MAX_LENGTH,
    DISPATCH_CODE_MAX_LENGTH,
    DISPATCH_DESCRIPTION_MAX_LENGTH,
    DISPATCH_PLAIN_DESCRIPTION_MAX_LENGTH,
)


class DispatchCode(Base):
    """Código de despacho do INPI explicado em linguagem simples (glossário e prazos dos alertas)."""

    __tablename__ = "dispatch_codes"
    # O mesmo código pode existir na seção de patentes e na de programas com sentidos diferentes.
    __table_args__ = (UniqueConstraint("asset_type", "code", name="uq_dispatch_codes_asset_type_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Código como publicado na RPI, guardado como texto (ex.: "16.1", "730").
    code: Mapped[str] = mapped_column(String(DISPATCH_CODE_MAX_LENGTH), index=True)
    # Seção da RPI: patentes (200) ou programas de computador (700).
    asset_type: Mapped[AssetType] = mapped_column(
        enum_column_type(AssetType, name="dispatch_code_asset_type", length=ASSET_TYPE_MAX_LENGTH)
    )
    official_description: Mapped[str] = mapped_column(String(DISPATCH_DESCRIPTION_MAX_LENGTH))
    plain_description: Mapped[str] = mapped_column(String(DISPATCH_PLAIN_DESCRIPTION_MAX_LENGTH))
    # Se exige ação do NIT; nesse caso deadline_days define o prazo contado da publicação.
    requires_action: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline_days: Mapped[int | None] = mapped_column(Integer, default=None)

    def __repr__(self) -> str:
        return f"<DispatchCode id={self.id} code={self.code!r} type={self.asset_type.value}>"
