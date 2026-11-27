from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, status

from app.models import Alert
from app.routes.deps import CurrentUser, DbSession
from app.schemas.alert import AlertRead, UnreadCount
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["Alertas"])


@router.get("/", response_model=list[AlertRead], summary="Lista os alertas do usuário logado (US12)")
def list_alerts(db: DbSession, user: CurrentUser, unread: bool = False, requires_action: bool = False) -> Sequence[Alert]:
    """Cada usuário vê só os próprios alertas. `unread=true` e `requires_action=true` filtram e podem ser combinados."""
    return alert_service.list_alerts_for(db, user, unread_only=unread, requires_action_only=requires_action)


@router.get("/unread-count", response_model=UnreadCount, summary="Quantidade de alertas não lidos (US12)")
def unread_count(db: DbSession, user: CurrentUser) -> UnreadCount:
    return UnreadCount(count=alert_service.count_unread_for(db, user))


@router.patch(
    "/{alert_id}/read",
    response_model=AlertRead,
    summary="Marca um alerta como lido (US12)",
    responses={404: {"description": "Alerta inexistente ou de outro usuário"}},
)
def mark_alert_as_read(alert_id: int, db: DbSession, user: CurrentUser) -> Alert:
    try:
        return alert_service.mark_as_read(db, user, alert_id)
    except alert_service.AlertNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
