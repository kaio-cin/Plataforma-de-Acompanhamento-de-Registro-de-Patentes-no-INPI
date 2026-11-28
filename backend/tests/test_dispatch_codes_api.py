"""Rota do glossário de despachos: qualquer usuário logado lê, em ordem natural de código e com filtro por tipo."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AssetType, DispatchCode, User
from tests.conftest import auth_header

URL = "/api/dispatch-codes/"


def _code(code: str, asset_type: AssetType = AssetType.PATENTE, **extra) -> DispatchCode:
    return DispatchCode(
        code=code,
        asset_type=asset_type,
        official_description=f"Descrição fictícia {code}",
        plain_description=f"Explicação fictícia {code}.",
        **extra,
    )


@pytest.fixture
def glossary(db_session: Session) -> None:
    # Inseridos fora de ordem, para a resposta provar que a API ordena.
    db_session.add_all(
        [
            _code("100", AssetType.PROGRAMA_DE_COMPUTADOR),
            _code("10.1"),
            _code("2.1"),
            _code("1.1.1"),
            _code("080", AssetType.PROGRAMA_DE_COMPUTADOR),
            _code("100"),
            _code("1.2", requires_action=True, deadline_days=60),
            _code("1.1"),
        ]
    )
    db_session.commit()


def _keys(response) -> list[tuple[str, str]]:
    return [(item["asset_type"], item["code"]) for item in response.json()]


def test_exige_login(client: TestClient, glossary: None) -> None:
    assert client.get(URL).status_code == 401


@pytest.mark.parametrize("email", ["nit@teste.edu.br", "autora@teste.edu.br"])
def test_nit_e_autor_veem_o_glossario_inteiro(
    client: TestClient, users: dict[str, User], glossary: None, email: str
) -> None:
    response = client.get(URL, headers=auth_header(client, email))

    assert response.status_code == 200
    assert len(response.json()) == 8


def test_ordena_por_tipo_e_em_ordem_natural_de_codigo(
    client: TestClient, users: dict[str, User], glossary: None
) -> None:
    response = client.get(URL, headers=auth_header(client, "nit@teste.edu.br"))

    assert _keys(response) == [
        ("Patente", "1.1"),
        ("Patente", "1.1.1"),
        ("Patente", "1.2"),
        ("Patente", "2.1"),
        ("Patente", "10.1"),
        ("Patente", "100"),
        ("Programa de Computador", "080"),
        ("Programa de Computador", "100"),
    ]


def test_devolve_os_campos_do_glossario(client: TestClient, users: dict[str, User], glossary: None) -> None:
    response = client.get(URL, headers=auth_header(client, "nit@teste.edu.br"))

    item = next(item for item in response.json() if item["code"] == "1.2")
    assert item == {
        "id": item["id"],
        "code": "1.2",
        "asset_type": "Patente",
        "official_description": "Descrição fictícia 1.2",
        "plain_description": "Explicação fictícia 1.2.",
        "requires_action": True,
        "deadline_days": 60,
    }


def test_filtra_por_tipo_de_ativo(client: TestClient, users: dict[str, User], glossary: None) -> None:
    response = client.get(
        URL, params={"asset_type": "Programa de Computador"}, headers=auth_header(client, "nit@teste.edu.br")
    )

    assert _keys(response) == [("Programa de Computador", "080"), ("Programa de Computador", "100")]


def test_recusa_tipo_de_ativo_desconhecido(client: TestClient, users: dict[str, User], glossary: None) -> None:
    response = client.get(URL, params={"asset_type": "Marca"}, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 422


def test_glossario_vazio_devolve_lista_vazia(client: TestClient, users: dict[str, User]) -> None:
    response = client.get(URL, headers=auth_header(client, "autora@teste.edu.br"))

    assert response.status_code == 200
    assert response.json() == []
