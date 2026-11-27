from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.columns import enum_column_type
from app.models.enums import RpiEditionStatus
from app.models.limits import (
    RPI_ERROR_MESSAGE_MAX_LENGTH,
    RPI_FILE_PATH_MAX_LENGTH,
    RPI_STATUS_MAX_LENGTH,
)

if TYPE_CHECKING:
    from app.models.dispatch import Dispatch


class RpiEdition(Base):
    """Edição semanal da Revista da Propriedade Industrial baixada pelo sistema (US08, US10)."""

    __tablename__ = "rpi_editions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Número da revista (ex.: 2862). Único: cada edição é baixada e processada uma vez só.
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    publication_date: Mapped[date] = mapped_column(Date)
    # Caminho local do XML baixado (pasta backend/data/rpi/, fora do Git).
    file_path: Mapped[str | None] = mapped_column(String(RPI_FILE_PATH_MAX_LENGTH), default=None)
    status: Mapped[RpiEditionStatus] = mapped_column(
        enum_column_type(RpiEditionStatus, name="rpi_edition_status", length=RPI_STATUS_MAX_LENGTH),
        default=RpiEditionStatus.BAIXADA,
    )
    # Quantidade de despachos da RPI que cruzaram com ativos cadastrados.
    dispatch_count: Mapped[int] = mapped_column(Integer, default=0)
    # Motivo da falha, preenchido quando o status é "Erro".
    error_message: Mapped[str | None] = mapped_column(String(RPI_ERROR_MESSAGE_MAX_LENGTH), default=None)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    # passive_deletes: o banco apaga os despachos (ON DELETE CASCADE) sem o ORM carregá-los antes.
    dispatches: Mapped[list[Dispatch]] = relationship(
        back_populates="edition", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<RpiEdition id={self.id} number={self.number} status={self.status.value}>"
