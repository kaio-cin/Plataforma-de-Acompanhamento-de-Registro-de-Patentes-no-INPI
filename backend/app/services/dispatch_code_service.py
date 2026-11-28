"""Consulta do glossário de códigos de despacho do INPI, independente da camada HTTP."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssetType, DispatchCode


def _code_order(code: str) -> tuple[tuple[int, int | str], ...]:
    """Ordem natural dos códigos: "2.1" antes de "10.1", "1.1" antes de "1.1.1" e de "1.2".

    Cada parte numérica é comparada como número; uma parte não numérica (não esperada) vai para o fim.
    """
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in code.split("."))


def list_dispatch_codes(db: Session, asset_type: AssetType | None = None) -> list[DispatchCode]:
    """Códigos do glossário, patentes antes de programas e cada tipo em ordem natural de código."""
    query = select(DispatchCode)
    if asset_type is not None:
        query = query.where(DispatchCode.asset_type == asset_type)
    type_order = {member: index for index, member in enumerate(AssetType)}
    return sorted(db.scalars(query), key=lambda row: (type_order[row.asset_type], _code_order(row.code)))
