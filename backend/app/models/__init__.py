"""Importa todos os models para registrá-los no metadata do SQLAlchemy."""

from app.models.alert import Alert
from app.models.asset import Asset
from app.models.dispatch import Dispatch
from app.models.dispatch_code import DispatchCode
from app.models.enums import AssetType, RpiEditionStatus, UserRole
from app.models.rpi_edition import RpiEdition
from app.models.user import User

__all__ = [
    "Alert",
    "Asset",
    "AssetType",
    "Dispatch",
    "DispatchCode",
    "RpiEdition",
    "RpiEditionStatus",
    "User",
    "UserRole",
]
