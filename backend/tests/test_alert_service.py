"""Alertas de despachos da RPI (US11–US13): model Alert, cálculo do prazo e create_alerts_for."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Alert, Asset, AssetType, Dispatch, DispatchCode, RpiEdition, User, UserRole
from app.services.alert_service import calculate_deadline, create_alerts_for

PUBLICACAO = date(2026, 11, 24)


@pytest.fixture
def edition(db_session: Session) -> RpiEdition:
    created = RpiEdition(number=2862, publication_date=PUBLICACAO)
    db_session.add(created)
    db_session.commit()
    return created


def _code(db_session: Session, *, requires_action: bool, deadline_days: int | None, code: str = "6.1") -> DispatchCode:
    created = DispatchCode(
        code=code,
        asset_type=AssetType.PATENTE,
        official_description="Exigência técnica",
        plain_description="O INPI pediu ajustes no pedido.",
        requires_action=requires_action,
        deadline_days=deadline_days,
    )
    db_session.add(created)
    db_session.commit()
    return created


def _dispatch(db_session: Session, edition: RpiEdition, asset: Asset, code: DispatchCode | None = None) -> Dispatch:
    created = Dispatch(
        edition=edition,
        asset=asset,
        process_number=asset.process_number,
        code=code.code if code else "99.9",
        dispatch_code=code,
        description="Exigência técnica",
        publication_date=edition.publication_date,
    )
    db_session.add(created)
    db_session.commit()
    return created


def _total_alerts(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(Alert))


def _recipient_ids(alerts: list[Alert]) -> set[int]:
    return {alert.user_id for alert in alerts}


# --- calculate_deadline ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("deadline_days", "esperado"),
    [
        (90, date(2027, 2, 22)),  # atravessa a virada do ano
        (60, date(2027, 1, 23)),
        (0, PUBLICACAO),
        (None, None),
    ],
)
def test_calcula_prazo_em_dias_corridos(deadline_days: int | None, esperado: date | None) -> None:
    assert calculate_deadline(PUBLICACAO, deadline_days) == esperado


# --- Destinatários (US13) --------------------------------------------------------------------------------------------


def test_avisa_o_nit_e_o_autor_vinculado(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    dispatch = _dispatch(db_session, edition, assets[0])  # ativo da autora

    created = create_alerts_for(db_session, dispatch)

    assert _recipient_ids(created) == {users["nit"].id, users["autora"].id}
    assert users["outro_autor"].id not in _recipient_ids(created)


def test_ativo_sem_autor_avisa_so_o_nit(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    dispatch = _dispatch(db_session, edition, assets[2])  # ativo sem autor vinculado

    created = create_alerts_for(db_session, dispatch)

    assert _recipient_ids(created) == {users["nit"].id}


def test_avisa_todos_os_usuarios_nit(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    segundo_nit = User(email="nit2@teste.edu.br", hashed_password=hash_password("x"), role=UserRole.NIT)
    db_session.add(segundo_nit)
    db_session.commit()
    dispatch = _dispatch(db_session, edition, assets[2])

    created = create_alerts_for(db_session, dispatch)

    assert _recipient_ids(created) == {users["nit"].id, segundo_nit.id}


def test_autor_que_tambem_e_nit_recebe_um_alerta_so(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    assets[2].author_user = users["nit"]
    db_session.commit()
    dispatch = _dispatch(db_session, edition, assets[2])

    created = create_alerts_for(db_session, dispatch)

    assert [alert.user_id for alert in created] == [users["nit"].id]


def test_reprocessar_nao_duplica_alertas(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    dispatch = _dispatch(db_session, edition, assets[0])
    create_alerts_for(db_session, dispatch)
    db_session.commit()

    segunda_vez = create_alerts_for(db_session, dispatch)

    assert segunda_vez == []
    assert _total_alerts(db_session) == 2


def test_reprocessar_avisa_so_quem_ainda_nao_foi_avisado(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    dispatch = _dispatch(db_session, edition, assets[2])
    create_alerts_for(db_session, dispatch)
    db_session.commit()
    assets[2].author_user = users["outro_autor"]
    db_session.commit()

    novos = create_alerts_for(db_session, dispatch)

    assert _recipient_ids(novos) == {users["outro_autor"].id}


def test_despacho_ainda_nao_gravado_tambem_gera_alertas(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    # O cruzamento da RPI pode chamar a função antes de gravar o despacho.
    dispatch = Dispatch(
        edition_id=edition.id,
        asset_id=assets[0].id,
        process_number=assets[0].process_number,
        code="6.1",
        description="Exigência técnica",
        publication_date=PUBLICACAO,
    )
    db_session.add(dispatch)

    created = create_alerts_for(db_session, dispatch)

    assert dispatch.id is not None
    assert _recipient_ids(created) == {users["nit"].id, users["autora"].id}


# --- Prazo e tipo do alerta ------------------------------------------------------------------------------------------


def test_codigo_que_exige_acao_gera_prazo(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    code = _code(db_session, requires_action=True, deadline_days=90)
    dispatch = _dispatch(db_session, edition, assets[0], code)

    created = create_alerts_for(db_session, dispatch)

    assert all(alert.requires_action for alert in created)
    assert {alert.deadline for alert in created} == {date(2027, 2, 22)}


def test_codigo_fora_do_glossario_gera_alerta_informativo_sem_prazo(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    dispatch = _dispatch(db_session, edition, assets[0], code=None)

    created = create_alerts_for(db_session, dispatch)

    assert len(created) == 2
    assert all(not alert.requires_action and alert.deadline is None for alert in created)


def test_codigo_que_exige_acao_sem_prazo_definido(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    code = _code(db_session, requires_action=True, deadline_days=None)
    dispatch = _dispatch(db_session, edition, assets[0], code)

    created = create_alerts_for(db_session, dispatch)

    assert all(alert.requires_action and alert.deadline is None for alert in created)


def test_codigo_informativo_nao_tem_prazo(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    code = _code(db_session, requires_action=False, deadline_days=30)
    dispatch = _dispatch(db_session, edition, assets[0], code)

    created = create_alerts_for(db_session, dispatch)

    assert all(not alert.requires_action and alert.deadline is None for alert in created)


def test_alerta_nasce_nao_lido_e_sem_email(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    dispatch = _dispatch(db_session, edition, assets[0])

    created = create_alerts_for(db_session, dispatch)
    db_session.commit()

    for alert in created:
        assert alert.is_read is False
        assert alert.email_sent is False
        assert alert.created_at is not None
        assert alert.dispatch.asset.id == assets[0].id


# --- Transação -------------------------------------------------------------------------------------------------------


def test_nao_faz_commit(db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition) -> None:
    dispatch = _dispatch(db_session, edition, assets[0])

    create_alerts_for(db_session, dispatch)
    db_session.rollback()

    assert _total_alerts(db_session) == 0


def test_banco_recusa_alerta_repetido(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    dispatch = _dispatch(db_session, edition, assets[0])
    db_session.add_all([Alert(user=users["nit"], dispatch=dispatch), Alert(user=users["nit"], dispatch=dispatch)])

    with pytest.raises(IntegrityError):
        db_session.commit()


# --- Cascata ---------------------------------------------------------------------------------------------------------


def test_apagar_despacho_apaga_os_alertas(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    dispatch = _dispatch(db_session, edition, assets[0])
    create_alerts_for(db_session, dispatch)
    db_session.commit()

    db_session.delete(dispatch)
    db_session.commit()

    assert _total_alerts(db_session) == 0


def test_apagar_edicao_apaga_os_alertas(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    create_alerts_for(db_session, _dispatch(db_session, edition, assets[0]))
    db_session.commit()

    db_session.delete(edition)
    db_session.commit()

    assert _total_alerts(db_session) == 0


def test_apagar_usuario_apaga_so_os_alertas_dele(
    db_session: Session, users: dict[str, User], assets: list[Asset], edition: RpiEdition
) -> None:
    create_alerts_for(db_session, _dispatch(db_session, edition, assets[0]))
    db_session.commit()

    db_session.delete(users["autora"])
    db_session.commit()
    db_session.expire_all()

    restantes = db_session.scalars(select(Alert.user_id)).all()
    assert restantes == [users["nit"].id]
