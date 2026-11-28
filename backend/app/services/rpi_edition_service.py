"""Consulta das edições da RPI registradas pelo sistema (US10)."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RpiEdition


def list_editions(db: Session) -> Sequence[RpiEdition]:
    """Todas as edições, da mais nova para a mais antiga (o número da RPI cresce toda semana)."""
    return db.scalars(select(RpiEdition).order_by(RpiEdition.number.desc())).all()


def get_edition(db: Session, edition_id: int) -> RpiEdition | None:
    return db.get(RpiEdition, edition_id)
