from datetime import date, timedelta

import pytest
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Asset, AssetType, User
from tests.conftest import auth_header

NOVO_ATIVO = {
    "title": "Método de compostagem acelerada",
    "asset_type": "Patente",
    "process_number": "br 10  2025   000999-9",
    "deposit_date": "2025-02-14",
    "status": "Em análise",
    "authors": "Fulano de Tal, Beltrana Souza",
}


# --- Listagem (US06 / US03) -------------------------------------------------


def test_nit_lista_todos_os_ativos(client: TestClient, assets) -> None:
    response = client.get("/api/assets/", headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_listagem_vem_ordenada_por_deposito_mais_recente(client: TestClient, assets) -> None:
    response = client.get("/api/assets/", headers=auth_header(client, "nit@teste.edu.br"))

    datas = [item["deposit_date"] for item in response.json()]
    assert datas == sorted(datas, reverse=True)


def test_autor_lista_apenas_os_proprios_ativos(client: TestClient, assets) -> None:
    response = client.get("/api/assets/", headers=auth_header(client, "autora@teste.edu.br"))

    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body] == ["Patente da autora"]
    assert body[0]["author_email"] == "autora@teste.edu.br"


def test_listagem_sem_login_retorna_401(client: TestClient, assets) -> None:
    assert client.get("/api/assets/").status_code == 401


# --- Cadastro (US04 / US07) -------------------------------------------------


def test_nit_cadastra_ativo_e_numero_do_processo_e_normalizado(client: TestClient, users) -> None:
    response = client.post("/api/assets/", json=NOVO_ATIVO, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 201
    body = response.json()
    assert body["process_number"] == "BR 10 2025 000999-9"
    assert body["author_user_id"] is None
    assert body["author_email"] is None


def test_ativo_cadastrado_aparece_na_listagem(client: TestClient, users) -> None:
    headers = auth_header(client, "nit@teste.edu.br")
    client.post("/api/assets/", json=NOVO_ATIVO, headers=headers)

    titulos = [item["title"] for item in client.get("/api/assets/", headers=headers).json()]
    assert NOVO_ATIVO["title"] in titulos


def test_cadastro_com_autor_vinculado_aparece_para_o_autor(client: TestClient, users) -> None:
    payload = {**NOVO_ATIVO, "author_email": "autora@teste.edu.br"}
    response = client.post("/api/assets/", json=payload, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 201
    assert response.json()["author_email"] == "autora@teste.edu.br"
    lista_autora = client.get("/api/assets/", headers=auth_header(client, "autora@teste.edu.br")).json()
    assert [item["title"] for item in lista_autora] == [NOVO_ATIVO["title"]]


def test_author_email_vazio_e_tratado_como_sem_autor(client: TestClient, users) -> None:
    payload = {**NOVO_ATIVO, "author_email": ""}
    response = client.post("/api/assets/", json=payload, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 201
    assert response.json()["author_email"] is None


def test_autor_nao_pode_cadastrar_ativo(client: TestClient, users) -> None:
    response = client.post("/api/assets/", json=NOVO_ATIVO, headers=auth_header(client, "autora@teste.edu.br"))

    assert response.status_code == 403


def test_processo_duplicado_retorna_409(client: TestClient, assets) -> None:
    payload = {**NOVO_ATIVO, "process_number": "BR 10 2023 000001-1"}
    response = client.post("/api/assets/", json=payload, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 409
    assert "BR 10 2023 000001-1" in response.json()["detail"]


def test_autor_inexistente_retorna_422(client: TestClient, users) -> None:
    payload = {**NOVO_ATIVO, "author_email": "naoexiste@teste.edu.br"}
    response = client.post("/api/assets/", json=payload, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 422


def test_vincular_usuario_nit_como_autor_retorna_422(client: TestClient, users) -> None:
    payload = {**NOVO_ATIVO, "author_email": "nit@teste.edu.br"}
    response = client.post("/api/assets/", json=payload, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 422


def test_natureza_invalida_retorna_422(client: TestClient, users) -> None:
    payload = {**NOVO_ATIVO, "asset_type": "Marca"}
    response = client.post("/api/assets/", json=payload, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 422


def test_data_de_deposito_no_futuro_retorna_422(client: TestClient, users) -> None:
    payload = {**NOVO_ATIVO, "deposit_date": (date.today() + timedelta(days=1)).isoformat()}
    response = client.post("/api/assets/", json=payload, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 422


# --- Detalhe (US05) ---------------------------------------------------------

ID_INEXISTENTE = 99999


def test_detalhe_nit_ve_ativo_de_outro_autor(client: TestClient, assets: list[Asset], users: dict[str, User]) -> None:
    ativo = assets[1]
    response = client.get(f"/api/assets/{ativo.id}", headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 200
    assert response.json() == {
        "id": ativo.id,
        "title": "Software de outro autor",
        "asset_type": "Programa de Computador",
        "process_number": "BR 51 2024 000002-2",
        "deposit_date": "2024-05-20",
        "status": "Registrado",
        "authors": "Outro Autor",
        "author_user_id": users["outro_autor"].id,
        "author_email": "outro@teste.edu.br",
    }


def test_detalhe_autor_ve_o_proprio_ativo(client: TestClient, assets: list[Asset]) -> None:
    response = client.get(f"/api/assets/{assets[0].id}", headers=auth_header(client, "autora@teste.edu.br"))

    assert response.status_code == 200
    assert response.json()["title"] == "Patente da autora"
    assert response.json()["author_email"] == "autora@teste.edu.br"


@pytest.mark.parametrize("indice", [1, 2], ids=["de_outro_autor", "sem_autor"])
def test_detalhe_autor_nao_ve_ativo_alheio(client: TestClient, assets: list[Asset], indice: int) -> None:
    response = client.get(f"/api/assets/{assets[indice].id}", headers=auth_header(client, "autora@teste.edu.br"))

    assert response.status_code == 404


@pytest.mark.parametrize("email", ["nit@teste.edu.br", "autora@teste.edu.br"], ids=["nit", "autor"])
def test_detalhe_de_id_inexistente_retorna_404(client: TestClient, assets: list[Asset], email: str) -> None:
    response = client.get(f"/api/assets/{ID_INEXISTENTE}", headers=auth_header(client, email))

    assert response.status_code == 404


def test_detalhe_404_de_ativo_alheio_igual_ao_de_inexistente(client: TestClient, assets: list[Asset]) -> None:
    headers = auth_header(client, "autora@teste.edu.br")

    alheio = client.get(f"/api/assets/{assets[1].id}", headers=headers)
    inexistente = client.get(f"/api/assets/{ID_INEXISTENTE}", headers=headers)

    assert alheio.status_code == inexistente.status_code == 404
    assert alheio.json() == inexistente.json() == {"detail": "Ativo não encontrado."}


def test_detalhe_sem_login_retorna_401(client: TestClient, assets: list[Asset]) -> None:
    assert client.get(f"/api/assets/{assets[0].id}").status_code == 401


@pytest.mark.xfail(strict=True, raises=ResponseValidationError, reason="DT-13")
def test_detalhe_de_ativo_antigo_fora_das_regras_retorna_200(client: TestClient, db_session: Session, users) -> None:
    # Ativo antigo gravado direto no banco, com título e processo abaixo do mínimo do cadastro.
    antigo = Asset(
        title="X",
        asset_type=AssetType.PATENTE,
        process_number="BR1",
        deposit_date=date(2010, 1, 1),
        status="?",
        authors="A",
    )
    db_session.add(antigo)
    db_session.commit()

    response = client.get(f"/api/assets/{antigo.id}", headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 200
    assert response.json()["title"] == "X"
