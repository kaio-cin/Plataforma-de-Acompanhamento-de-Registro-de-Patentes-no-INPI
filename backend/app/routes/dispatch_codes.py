from fastapi import APIRouter

from app.models import AssetType, DispatchCode
from app.routes.deps import CurrentUser, DbSession
from app.schemas.dispatch_code import DispatchCodeRead
from app.services import dispatch_code_service

router = APIRouter(prefix="/dispatch-codes", tags=["Glossário"])


@router.get("/", response_model=list[DispatchCodeRead], summary="Glossário de códigos de despacho do INPI")
def list_dispatch_codes(db: DbSession, _user: CurrentUser, asset_type: AssetType | None = None) -> list[DispatchCode]:
    """Todos os perfis veem o glossário inteiro. `asset_type` filtra por patentes ou programas de computador."""
    return dispatch_code_service.list_dispatch_codes(db, asset_type)
