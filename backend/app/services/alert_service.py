"""Regras dos alertas de despachos da RPI (US11–US13), independentes da camada HTTP."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Dispatch, User, UserRole


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
