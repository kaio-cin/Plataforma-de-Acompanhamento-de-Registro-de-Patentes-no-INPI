"""Rotas de alertas (US12): cada usuário vê e altera só os próprios alertas, com filtros e contador."""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Asset, AssetType, Dispatch, DispatchCode, RpiEdition, User
from app.services.alert_service import create_alerts_for
from tests.conftest import auth_header

NIT = "nit@teste.edu.br"
AUTORA = "autora@teste.edu.br"
OUTRO_AUTOR = "outro@teste.edu.br"
EXPLICACAO_6_1 = "O INPI pediu ajustes no pedido. É preciso responder dentro do prazo."


def _dispatch(edition: RpiEdition, asset: Asset, code: str, description: str, glossary: DispatchCode | None) -> Dispatch:
    return Dispatch(
        edition=edition,
        asset=asset,
        process_number=asset.process_number,
        code=code,
        dispatch_code=glossary,
        description=description,
        publication_date=edition.publication_date,
    )


@pytest.fixture
def dispatches(db_session: Session, users: dict[str, User], assets: list[Asset]) -> dict[str, Dispatch]:
    """Três despachos, criados em dias diferentes para a ordem da lista ser previsível.

    - "exigencia": ativo da autora, exige ação com prazo  -> alertas do NIT e da autora
    - "sem_glossario": ativo sem autor, código fora do glossário -> alerta só do NIT (já lido)
    - "informativo": ativo do outro autor, código informativo -> alertas do NIT e do outro autor
    """
    edition = RpiEdition(number=2862, publication_date=date(2026, 11, 24))
    exige = DispatchCode(
        code="6.1",
        asset_type=AssetType.PATENTE,
        official_description="Exigência técnica",
        plain_description=EXPLICACAO_6_1,
        requires_action=True,
        deadline_days=90,
    )
    informa = DispatchCode(
        code="730",
        asset_type=AssetType.PROGRAMA_DE_COMPUTADOR,
        official_description="Registro concedido",
        plain_description="O registro do programa foi concedido.",
        requires_action=False,
    )
    created = {
        "exigencia": _dispatch(edition, assets[0], "6.1", "Exigência técnica", exige),
        "sem_glossario": _dispatch(edition, assets[2], "99.9", "Despacho desconhecido", None),
        "informativo": _dispatch(edition, assets[1], "730", "Registro concedido", informa),
    }
    db_session.add_all(created.values())
    for day, dispatch in zip((25, 26, 27), created.values(), strict=True):
        for alert in create_alerts_for(db_session, dispatch):
            alert.created_at = datetime(2026, 11, day, 10, 0)
    db_session.commit()

    _alert(db_session, users["nit"], created["sem_glossario"]).is_read = True
    db_session.commit()
    return created


def _alert(db_session: Session, user: User, dispatch: Dispatch) -> Alert:
    return db_session.scalar(select(Alert).where(Alert.user_id == user.id, Alert.dispatch_id == dispatch.id))


def _codes(response) -> list[str]:
    return [item["dispatch_code"] for item in response.json()]


# --- Autenticação ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/alerts/"), ("get", "/api/alerts/unread-count"), ("patch", "/api/alerts/1/read")],
)
def test_rotas_exigem_login(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


# --- Listagem: cada um vê só os próprios -----------------------------------------------------------------------------


def test_nit_ve_os_proprios_alertas_do_mais_novo_ao_mais_antigo(client: TestClient, dispatches) -> None:
    response = client.get("/api/alerts/", headers=auth_header(client, NIT))

    assert response.status_code == 200
    assert _codes(response) == ["730", "99.9", "6.1"]


def test_autora_ve_so_os_proprios_alertas(client: TestClient, dispatches) -> None:
    response = client.get("/api/alerts/", headers=auth_header(client, AUTORA))

    assert _codes(response) == ["6.1"]


def test_outro_autor_nao_ve_alertas_da_autora(client: TestClient, dispatches) -> None:
    response = client.get("/api/alerts/", headers=auth_header(client, OUTRO_AUTOR))

    assert _codes(response) == ["730"]


def test_usuario_sem_alertas_recebe_lista_vazia(client: TestClient, users) -> None:
    response = client.get("/api/alerts/", headers=auth_header(client, NIT))

    assert response.status_code == 200
    assert response.json() == []


def test_campos_do_alerta(client: TestClient, users: dict[str, User], assets: list[Asset], dispatches) -> None:
    response = client.get("/api/alerts/", headers=auth_header(client, AUTORA))

    alerta = response.json()[0]
    assert isinstance(alerta["id"], int)
    assert alerta["created_at"].startswith("2026-11-25T10:00")
    del alerta["id"], alerta["created_at"]
    assert alerta == {
        "asset_id": assets[0].id,
        "asset_title": "Patente da autora",
        "process_number": "BR 10 2023 000001-1",
        "dispatch_code": "6.1",
        "dispatch_description": "Exigência técnica",
        "dispatch_plain_description": EXPLICACAO_6_1,
        "publication_date": "2026-11-24",
        "requires_action": True,
        "deadline": "2027-02-22",
        "is_read": False,
    }


def test_codigo_fora_do_glossario_vem_sem_explicacao_e_sem_prazo(client: TestClient, dispatches) -> None:
    response = client.get("/api/alerts/", headers=auth_header(client, NIT))

    sem_glossario = next(item for item in response.json() if item["dispatch_code"] == "99.9")
    assert sem_glossario["dispatch_plain_description"] is None
    assert sem_glossario["deadline"] is None
    assert sem_glossario["requires_action"] is False


# --- Filtros ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "esperado"),
    [
        ("?unread=true", ["730", "6.1"]),
        ("?requires_action=true", ["6.1"]),
        ("?unread=true&requires_action=true", ["6.1"]),
        ("?unread=false&requires_action=false", ["730", "99.9", "6.1"]),
    ],
)
def test_filtros(client: TestClient, dispatches, query: str, esperado: list[str]) -> None:
    response = client.get(f"/api/alerts/{query}", headers=auth_header(client, NIT))

    assert response.status_code == 200
    assert _codes(response) == esperado


def test_filtro_invalido_responde_422(client: TestClient, dispatches) -> None:
    response = client.get("/api/alerts/?unread=talvez", headers=auth_header(client, NIT))

    assert response.status_code == 422


# --- Contador --------------------------------------------------------------------------------------------------------


def test_contador_de_nao_lidos(client: TestClient, dispatches) -> None:
    assert client.get("/api/alerts/unread-count", headers=auth_header(client, NIT)).json() == {"count": 2}
    assert client.get("/api/alerts/unread-count", headers=auth_header(client, AUTORA)).json() == {"count": 1}


def test_contador_zerado_sem_alertas(client: TestClient, users) -> None:
    assert client.get("/api/alerts/unread-count", headers=auth_header(client, NIT)).json() == {"count": 0}


# --- Marcar como lido ------------------------------------------------------------------------------------------------


def test_marca_o_proprio_alerta_como_lido(
    client: TestClient, db_session: Session, users: dict[str, User], dispatches
) -> None:
    headers = auth_header(client, AUTORA)
    alerta = _alert(db_session, users["autora"], dispatches["exigencia"])

    response = client.patch(f"/api/alerts/{alerta.id}/read", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == alerta.id
    assert response.json()["is_read"] is True
    db_session.expire_all()
    assert _alert(db_session, users["autora"], dispatches["exigencia"]).is_read is True
    assert client.get("/api/alerts/unread-count", headers=headers).json() == {"count": 0}


def test_marcar_de_novo_nao_e_erro(client: TestClient, db_session: Session, users: dict[str, User], dispatches) -> None:
    headers = auth_header(client, NIT)
    ja_lido = _alert(db_session, users["nit"], dispatches["sem_glossario"])

    response = client.patch(f"/api/alerts/{ja_lido.id}/read", headers=headers)

    assert response.status_code == 200
    assert response.json()["is_read"] is True


def test_nao_marca_alerta_de_outro_usuario(
    client: TestClient, db_session: Session, users: dict[str, User], dispatches
) -> None:
    da_autora = _alert(db_session, users["autora"], dispatches["exigencia"])

    response = client.patch(f"/api/alerts/{da_autora.id}/read", headers=auth_header(client, OUTRO_AUTOR))

    assert response.status_code == 404
    assert response.json()["detail"] == "Alerta não encontrado."
    db_session.expire_all()
    assert _alert(db_session, users["autora"], dispatches["exigencia"]).is_read is False


def test_nit_tambem_nao_marca_alerta_de_outro_usuario(
    client: TestClient, db_session: Session, users: dict[str, User], dispatches
) -> None:
    da_autora = _alert(db_session, users["autora"], dispatches["exigencia"])

    response = client.patch(f"/api/alerts/{da_autora.id}/read", headers=auth_header(client, NIT))

    assert response.status_code == 404


def test_alerta_inexistente_responde_404(client: TestClient, dispatches) -> None:
    response = client.patch("/api/alerts/99999/read", headers=auth_header(client, NIT))

    assert response.status_code == 404
    assert response.json()["detail"] == "Alerta não encontrado."


# --- DT-13: a saída não revalida as regras de entrada ----------------------------------------------------------------


def test_dado_fora_das_regras_atuais_nao_derruba_a_lista(
    client: TestClient, db_session: Session, users: dict[str, User]
) -> None:
    # Ativo antigo gravado direto no banco, com título e processo abaixo do mínimo do cadastro.
    antigo = Asset(
        title="X",
        asset_type=AssetType.PATENTE,
        process_number="BR1",
        deposit_date=date(2010, 1, 1),
        status="?",
        authors="A",
        author_user=users["autora"],
    )
    edition = RpiEdition(number=2000, publication_date=date(2026, 11, 24))
    dispatch = _dispatch(edition, antigo, "6.1", "", None)
    db_session.add_all([antigo, dispatch])
    create_alerts_for(db_session, dispatch)
    db_session.commit()

    response = client.get("/api/alerts/", headers=auth_header(client, AUTORA))

    assert response.status_code == 200
    assert response.json()[0]["asset_title"] == "X"
