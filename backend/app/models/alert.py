from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dispatch import Dispatch
    from app.models.user import User


def _utc_now() -> datetime:
    # Gravado sem fuso (UTC), como as demais colunas DateTime do projeto.
    return datetime.now(UTC).replace(tzinfo=None)


class Alert(Base):
    """Aviso de um despacho da RPI para um usuário: NIT ou autor vinculado ao ativo (US11–US13).

    O ativo não é copiado para cá: ele vem de dispatch.asset.
    """

    __tablename__ = "alerts"
    # Reprocessar a mesma edição não avisa o mesmo usuário duas vezes sobre o mesmo despacho.
    __table_args__ = (UniqueConstraint("user_id", "dispatch_id", name="uq_alerts_user_dispatch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # CASCADE: apagar o usuário ou o despacho apaga os alertas ligados a ele.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatches.id", ondelete="CASCADE"), index=True)
    # Copiados do glossário na criação: se o código mudar ou for apagado, o alerta mantém o que valia.
    requires_action: Mapped[bool] = mapped_column(Boolean, default=False)
    # Data limite (publicação + prazo em dias corridos); vazia quando não há prazo.
    deadline: Mapped[date | None] = mapped_column(Date, default=None)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    user: Mapped[User] = relationship()
    dispatch: Mapped[Dispatch] = relationship()

    # Dados do despacho e do ativo expostos diretamente na resposta da API (US12).
    @property
    def asset_id(self) -> int:
        return self.dispatch.asset_id

    @property
    def asset_title(self) -> str:
        return self.dispatch.asset.title

    @property
    def process_number(self) -> str:
        """Número do processo como cadastrado (não o texto cru da RPI)."""
        return self.dispatch.asset.process_number

    @property
    def dispatch_code(self) -> str:
        return self.dispatch.code

    @property
    def dispatch_description(self) -> str:
        return self.dispatch.description

    @property
    def dispatch_plain_description(self) -> str | None:
        """Explicação em linguagem simples do glossário; vazia se o código não estiver nele."""
        code = self.dispatch.dispatch_code
        return code.plain_description if code is not None else None

    @property
    def publication_date(self) -> date:
        return self.dispatch.publication_date

    def __repr__(self) -> str:
        return f"<Alert id={self.id} user={self.user_id} dispatch={self.dispatch_id} read={self.is_read}>"
