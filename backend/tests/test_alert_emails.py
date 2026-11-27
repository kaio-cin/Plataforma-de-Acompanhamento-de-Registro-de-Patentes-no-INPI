"""Envio dos e-mails pendentes dos alertas (US11): reserva, falhas e gravação, sem rede."""

from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Alert, Asset, Dispatch, RpiEdition, User
from app.services import email_service
from app.services.alert_service import create_alerts_for, send_pending_alert_emails

Envio = tuple[str, str, str]


@pytest.fixture
def edition(db_session: Session) -> RpiEdition:
    created = RpiEdition(number=2862, publication_date=date(2026, 11, 24))
    db_session.add(created)
    db_session.commit()
    return created


@pytest.fixture
def alerts(db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition) -> list[Alert]:
    """Dois alertas do mesmo despacho: um para o NIT e outro para a autora."""
    dispatch = Dispatch(
        edition=edition,
        asset=assets[0],
        process_number=assets[0].process_number,
        code="6.1",
        description="Exigência técnica",
        publication_date=edition.publication_date,
    )
    db_session.add(dispatch)
    created = create_alerts_for(db_session, dispatch)
    db_session.commit()
    return created


@pytest.fixture
def enviados(monkeypatch: pytest.MonkeyPatch) -> list[Envio]:
    """Troca send_email por um falso que registra os envios e sempre dá certo."""
    registro: list[Envio] = []

    def fake_send_email(to: str, subject: str, body: str) -> bool:
        registro.append((to, subject, body))
        return True

    monkeypatch.setattr(email_service, "send_email", fake_send_email)
    return registro


def _use_send_email(monkeypatch: pytest.MonkeyPatch, fake: Callable[[str, str, str], bool]) -> None:
    monkeypatch.setattr(email_service, "send_email", fake)


def _email_sent_no_banco(db_session: Session) -> dict[int, bool]:
    """Lê email_sent direto do banco, ignorando o que está em memória na sessão."""
    db_session.expire_all()
    return dict(db_session.execute(select(Alert.user_id, Alert.email_sent)).all())


# --- Envio normal ----------------------------------------------------------------------------------------------------


def test_envia_os_pendentes_para_o_email_de_cada_destinatario(
    db_session: Session, users: dict[str, User], alerts: list[Alert], enviados: list[Envio]
) -> None:
    total = send_pending_alert_emails(db_session)

    assert total == 2
    assert {to for to, _s, _b in enviados} == {"nit@teste.edu.br", "autora@teste.edu.br"}
    assert all(subject.startswith("[Radar INPI]") for _to, subject, _b in enviados)
    assert _email_sent_no_banco(db_session) == {users["nit"].id: True, users["autora"].id: True}


def test_segunda_chamada_nao_reenvia(db_session: Session, alerts: list[Alert], enviados: list[Envio]) -> None:
    send_pending_alert_emails(db_session)

    assert send_pending_alert_emails(db_session) == 0
    assert len(enviados) == 2


def test_sem_pendentes_nao_envia_nada(db_session: Session, users: dict[str, User], enviados: list[Envio]) -> None:
    assert send_pending_alert_emails(db_session) == 0
    assert enviados == []


def test_alerta_ja_enviado_fica_de_fora(
    db_session: Session, users: dict[str, User], alerts: list[Alert], enviados: list[Envio]
) -> None:
    db_session.execute(update(Alert).where(Alert.user_id == users["nit"].id).values(email_sent=True))
    db_session.commit()

    assert send_pending_alert_emails(db_session) == 1
    assert [to for to, _s, _b in enviados] == ["autora@teste.edu.br"]


def test_marcacoes_continuam_gravadas_depois_de_rollback(
    db_session: Session, users: dict[str, User], alerts: list[Alert], enviados: list[Envio]
) -> None:
    send_pending_alert_emails(db_session)

    db_session.rollback()

    assert _email_sent_no_banco(db_session) == {users["nit"].id: True, users["autora"].id: True}


# --- Reserva ---------------------------------------------------------------------------------------------------------


def test_alerta_reservado_por_outra_chamada_nao_e_enviado_de_novo(
    monkeypatch: pytest.MonkeyPatch, db_session: Session, users: dict[str, User], alerts: list[Alert]
) -> None:
    enviados: list[str] = []
    autora = users["autora"].id

    def fake_send_email(to: str, _subject: str, _body: str) -> bool:
        enviados.append(to)
        # Simula outra chamada simultânea que reserva o alerta da autora enquanto este envio acontece.
        db_session.execute(update(Alert).where(Alert.user_id == autora).values(email_sent=True))
        db_session.commit()
        return True

    _use_send_email(monkeypatch, fake_send_email)

    total = send_pending_alert_emails(db_session)

    assert total == 1
    assert enviados == ["nit@teste.edu.br"]  # a autora ficou com a outra chamada


def test_alerta_ja_esta_reservado_durante_o_envio(
    monkeypatch: pytest.MonkeyPatch, db_session: Session, users: dict[str, User], alerts: list[Alert]
) -> None:
    estado_durante_o_envio: list[bool] = []

    def fake_send_email(to: str, _subject: str, _body: str) -> bool:
        user_id = db_session.scalar(select(User.id).where(User.email == to))
        estado_durante_o_envio.append(db_session.scalar(select(Alert.email_sent).where(Alert.user_id == user_id)))
        return True

    _use_send_email(monkeypatch, fake_send_email)

    send_pending_alert_emails(db_session)

    assert estado_durante_o_envio == [True, True]


# --- Falhas ----------------------------------------------------------------------------------------------------------


def test_falha_devolve_o_alerta_para_a_fila_e_os_outros_continuam(
    monkeypatch: pytest.MonkeyPatch, db_session: Session, users: dict[str, User], alerts: list[Alert]
) -> None:
    tentativas: list[str] = []

    def fake_send_email(to: str, _subject: str, _body: str) -> bool:
        tentativas.append(to)
        return to != "nit@teste.edu.br"  # o SMTP recusa só o e-mail do NIT

    _use_send_email(monkeypatch, fake_send_email)

    total = send_pending_alert_emails(db_session)

    assert total == 1
    assert set(tentativas) == {"nit@teste.edu.br", "autora@teste.edu.br"}
    assert _email_sent_no_banco(db_session) == {users["nit"].id: False, users["autora"].id: True}


def test_alerta_que_falhou_e_reenviado_na_proxima_chamada(
    monkeypatch: pytest.MonkeyPatch, db_session: Session, users: dict[str, User], alerts: list[Alert]
) -> None:
    _use_send_email(monkeypatch, lambda to, _s, _b: to != "nit@teste.edu.br")
    send_pending_alert_emails(db_session)

    reenviados: list[str] = []

    def fake_send_email(to: str, _subject: str, _body: str) -> bool:
        reenviados.append(to)
        return True

    _use_send_email(monkeypatch, fake_send_email)

    assert send_pending_alert_emails(db_session) == 1
    assert reenviados == ["nit@teste.edu.br"]


def test_erro_inesperado_num_alerta_nao_interrompe_os_outros(
    monkeypatch: pytest.MonkeyPatch, db_session: Session, users: dict[str, User], alerts: list[Alert]
) -> None:
    def fake_send_email(to: str, _subject: str, _body: str) -> bool:
        if to == "nit@teste.edu.br":
            raise RuntimeError("erro inesperado")
        return True

    _use_send_email(monkeypatch, fake_send_email)

    assert send_pending_alert_emails(db_session) == 1
    assert _email_sent_no_banco(db_session) == {users["nit"].id: False, users["autora"].id: True}
