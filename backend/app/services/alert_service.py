"""Regras dos alertas de despachos da RPI (US11–US13), independentes da camada HTTP."""

import logging
from datetime import date, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models import Alert, Dispatch, User, UserRole
from app.services import email_service
from app.services.alert_message import build_alert_email

logger = logging.getLogger(__name__)


def calculate_deadline(publication_date: date, deadline_days: int | None) -> date | None:
    """Data limite para agir: publicação na RPI mais o prazo em dias corridos.

    Sem prazo (deadline_days vazio), não há data limite. Fins de semana e feriados não são
    descontados (simplificação combinada com o grupo).
    """
    if deadline_days is None:
        return None
    return publication_date + timedelta(days=deadline_days)


def create_alerts_for(db: Session, dispatch: Dispatch) -> list[Alert]:
    """Cria um alerta do despacho para cada usuário NIT e para o autor vinculado ao ativo (US13).

    - Ninguém recebe dois alertas do mesmo despacho: o autor que também é NIT recebe um só, e
      chamar de novo (reprocessar a edição) não repete quem já foi avisado.
    - Despacho com código fora do glossário vira alerta informativo, sem prazo.
    - Só exige ação e só tem prazo o despacho cujo código exige ação.
    - Não faz commit nem envia e-mail: quem chama decide quando gravar a edição inteira.

    Retorna apenas os alertas criados nesta chamada.
    """
    # Garante que o despacho tenha id e que ativo e código possam ser carregados.
    db.flush()

    recipients: dict[int, User] = {
        user.id: user for user in db.scalars(select(User).where(User.role == UserRole.NIT).order_by(User.id))
    }
    author = dispatch.asset.author_user
    if author is not None:
        recipients.setdefault(author.id, author)

    already_alerted = set(db.scalars(select(Alert.user_id).where(Alert.dispatch_id == dispatch.id)))

    code = dispatch.dispatch_code
    requires_action = code is not None and code.requires_action
    deadline = calculate_deadline(dispatch.publication_date, code.deadline_days) if requires_action else None

    created = [
        Alert(user=user, dispatch=dispatch, requires_action=requires_action, deadline=deadline)
        for user_id, user in recipients.items()
        if user_id not in already_alerted
    ]
    db.add_all(created)
    db.flush()
    return created


def _reserve_for_sending(db: Session, alert_id: int) -> bool:
    """Marca o alerta como enviado antes do envio, só se ninguém o reservou antes.

    O UPDATE condicional é atômico no banco: se duas chamadas rodarem ao mesmo tempo (agendamento
    e botão "Processar agora"), só uma consegue a reserva e o e-mail sai uma vez só.
    """
    result = db.execute(
        update(Alert).where(Alert.id == alert_id, Alert.email_sent.is_(False)).values(email_sent=True)
    )
    db.commit()
    return result.rowcount == 1


def _release(db: Session, alert_id: int) -> None:
    """Devolve o alerta para a fila de envio depois de uma falha."""
    db.execute(update(Alert).where(Alert.id == alert_id).values(email_sent=False))
    db.commit()


def send_pending_alert_emails(db: Session) -> int:
    """Envia por e-mail os alertas ainda não enviados e retorna quantos e-mails saíram (US11).

    - Cada alerta é reservado (email_sent=True, com commit) antes do envio: chamadas simultâneas
      não enviam o mesmo e-mail duas vezes.
    - Se o envio falhar, o alerta volta para email_sent=False e será tentado na próxima chamada.
    - Uma falha não interrompe os demais envios nem levanta exceção.
    - Se o processo cair entre a reserva e o envio, esse e-mail se perde, mas o alerta continua
      no painel (US12): é preferível a mandar e-mails repetidos.

    Faz commit a cada alerta; chame depois de gravar a edição da RPI.
    """
    pending_ids = list(
        db.scalars(select(Alert.id).where(Alert.email_sent.is_(False)).order_by(Alert.created_at, Alert.id))
    )

    sent = 0
    for alert_id in pending_ids:
        if not _reserve_for_sending(db, alert_id):
            continue  # outra chamada já reservou este alerta

        alert = db.scalars(
            select(Alert)
            .where(Alert.id == alert_id)
            .options(
                selectinload(Alert.user),
                selectinload(Alert.dispatch).selectinload(Dispatch.asset),
                selectinload(Alert.dispatch).selectinload(Dispatch.dispatch_code),
            )
        ).one_or_none()
        if alert is None:
            continue  # apagado depois de reservado (ex.: edição removida)

        try:
            subject, body = build_alert_email(alert)
            delivered = email_service.send_email(alert.user.email, subject, body)
        except Exception:
            # Defesa extra: um dado inesperado num alerta não pode impedir os outros envios.
            logger.exception("Erro ao preparar o e-mail do alerta %s", alert_id)
            delivered = False

        if delivered:
            sent += 1
        else:
            _release(db, alert_id)
    return sent
