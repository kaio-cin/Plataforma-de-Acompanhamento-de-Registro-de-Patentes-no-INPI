from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.limits import (
    DISPATCH_CODE_MAX_LENGTH,
    DISPATCH_DESCRIPTION_MAX_LENGTH,
    PROCESS_NUMBER_MAX_LENGTH,
)

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.dispatch_code import DispatchCode
    from app.models.rpi_edition import RpiEdition


class Dispatch(Base):
    """Despacho publicado na RPI para um processo cadastrado (US09).

    Só são gravados os despachos que cruzaram com um ativo, por isso asset_id é obrigatório.
    """

    __tablename__ = "dispatches"
    # Reprocessar a mesma edição não duplica despachos.
    __table_args__ = (
        UniqueConstraint("edition_id", "process_number", "code", name="uq_dispatches_edition_process_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # CASCADE: apagar a edição ou o ativo apaga os despachos ligados a ele.
    edition_id: Mapped[int] = mapped_column(ForeignKey("rpi_editions.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    # Número do processo como veio na RPI, antes da normalização usada no cruzamento.
    process_number: Mapped[str] = mapped_column(String(PROCESS_NUMBER_MAX_LENGTH), index=True)
    # Código como veio no XML; a ligação com o glossário é opcional, para um código
    # que ainda não está em dispatch_codes não impedir o processamento.
    code: Mapped[str] = mapped_column(String(DISPATCH_CODE_MAX_LENGTH))
    dispatch_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("dispatch_codes.id", ondelete="SET NULL"), index=True, default=None
    )
    description: Mapped[str] = mapped_column(String(DISPATCH_DESCRIPTION_MAX_LENGTH))
    complement: Mapped[str | None] = mapped_column(Text, default=None)
    # Cópia da data da edição: ordena a linha do tempo e calcula o prazo do alerta sem join.
    publication_date: Mapped[date] = mapped_column(Date)

    edition: Mapped[RpiEdition] = relationship(back_populates="dispatches")
    asset: Mapped[Asset] = relationship()
    dispatch_code: Mapped[DispatchCode | None] = relationship()

    def __repr__(self) -> str:
        return f"<Dispatch id={self.id} process={self.process_number!r} code={self.code!r}>"
