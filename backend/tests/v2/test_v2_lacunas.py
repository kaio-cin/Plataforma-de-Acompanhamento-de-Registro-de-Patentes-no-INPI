"""Suíte v2 — testes que fecham as lacunas G1…G6 encontradas na análise da v1.

Origem: gerados pela LLM na rodada 1 da v2 (docs/testes/prompts/v2-rodada-1.md) e revisados pela equipe contra
os critérios de aceitação. Mudanças da revisão estão marcadas com "Revisão da equipe".
Cada teste indica a lacuna que resolve, o critério de aceitação e a técnica aplicada.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import create_app
from tests.conftest import auth_header

ASSETS_URL = "/api/assets/"
ME_URL = "/api/auth/me"

ATIVO_VALIDO = {
    "title": "Método de compostagem acelerada",
    "asset_type": "Patente",
    "process_number": "BR 10 2025 000999-9",
    "deposit_date": "2025-02-14",
    "status": "Em análise",
    "authors": "Fulano de Tal, Beltrana Souza",
}

# Revisão da equipe: os casos abaixo expõem o BUG-01 (docs/testes/defeitos.md). O oráculo continua sendo o do
# requisito (422 / 200); o xfail estrito documenta o defeito conhecido e passa a falhar assim que ele for corrigido,
# obrigando a remover a marcação.
BUG_01 = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BUG-01: tamanho mínimo é validado antes de normalizar os espaços (docs/testes/defeitos.md)",
)


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    """Cliente que devolve 500 em vez de propagar a exceção do servidor.

    Revisão da equipe: com o `client` padrão, o defeito aparece como exceção (ResponseValidationError) e o teste
    "quebra" em vez de falhar na asserção. Aqui vemos o que o usuário vê: o código HTTP.
    """
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(application, raise_server_exceptions=False)


@pytest.fixture
def nit(api: TestClient, users) -> dict[str, str]:
    return auth_header(api, "nit@teste.edu.br")


def _cadastrar(api: TestClient, headers: dict[str, str], **campos):
    return api.post(ASSETS_URL, json={**ATIVO_VALIDO, **campos}, headers=headers)


# ------------------------------------------------------------------ G1 — partição "somente espaços"


# G1 / US04 — CA04-3, CA04-4, CA04-7, CA04-8 — partição inválida: campo só com espaços (tamanho bruto ≥ mínimo)
@BUG_01
@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("title", "     "),  # P23: 5 espaços (mínimo bruto 3)
        ("process_number", "       "),  # P33: 7 espaços (mínimo bruto 5)
        ("status", "    "),  # P40: 4 espaços (mínimo bruto 2)
        ("authors", "    "),  # P44: 4 espaços (mínimo bruto 2)
    ],
)
def test_campo_so_com_espacos_retorna_422(api: TestClient, nit, campo: str, valor: str) -> None:
    response = _cadastrar(api, nit, **{campo: valor})

    assert response.status_code == 422


# G1 / US06 — CA06-1 — partição inválida no cadastro não pode derrubar a listagem da carteira
@BUG_01
def test_cadastro_invalido_nao_deixa_a_carteira_indisponivel(api: TestClient, nit, assets) -> None:
    _cadastrar(api, nit, title="     ")

    response = api.get(ASSETS_URL, headers=nit)

    assert response.status_code == 200
    assert len(response.json()) == len(assets)


# ------------------------------------------------------------------ G2 — limites do título efetivo (L13)


# G2 / US04 — CA04-3 — valor-limite (L13): 2 caracteres efetivos com espaços nas bordas → 422
@BUG_01
def test_titulo_com_2_caracteres_efetivos_retorna_422(api: TestClient, nit) -> None:
    response = _cadastrar(api, nit, title="  ab  ")

    assert response.status_code == 422


# G2 / US04 — CA04-3 — valor-limite (L13): 3 caracteres efetivos com espaços nas bordas → 201
def test_titulo_com_3_caracteres_efetivos_e_aceito_e_normalizado(api: TestClient, nit) -> None:
    response = _cadastrar(api, nit, title="  abc  ")

    assert response.status_code == 201
    assert response.json()["title"] == "abc"


# G2 / US04 — CA04-3 — valor-limite superior efetivo: 500 caracteres + espaços nas bordas → 201
@BUG_01
def test_titulo_com_500_caracteres_efetivos_e_espacos_nas_bordas_e_aceito(api: TestClient, nit) -> None:
    response = _cadastrar(api, nit, title="  " + "a" * 500 + "  ")

    assert response.status_code == 201
    assert response.json()["title"] == "a" * 500


# ------------------------------------------------------------------ G3 — ordenação com empate (L12)


# G3 / US06 — CA06-2 — critério de aceitação: ordem exata dos três ativos da fixture
def test_ordem_exata_da_carteira_por_data_de_deposito(api: TestClient, nit, assets) -> None:
    response = api.get(ASSETS_URL, headers=nit)

    assert [item["process_number"] for item in response.json()] == [
        "BR 51 2024 000002-2",  # 2024-05-20
        "BR 10 2023 000001-1",  # 2023-01-10
        "BR 10 2022 000003-3",  # 2022-08-01
    ]


# G3 / US06 — CA06-2 — valor-limite (L12): mesma data de depósito → o cadastrado por último vem primeiro
def test_empate_de_data_mostra_o_cadastrado_por_ultimo_primeiro(api: TestClient, nit, assets) -> None:
    novo = _cadastrar(api, nit, deposit_date="2024-05-20").json()  # mesma data do "Software de outro autor"

    ordem = [item["process_number"] for item in api.get(ASSETS_URL, headers=nit).json()]

    assert ordem[:2] == [novo["process_number"], "BR 51 2024 000002-2"]


# ------------------------------------------------------------------ G4 — valores dos itens da listagem


# G4 / US06 — CA06-3 — critério de aceitação: cada item traz os valores gravados, inclusive o status atual
def test_itens_da_listagem_trazem_os_valores_gravados(api: TestClient, nit, assets) -> None:
    por_processo = {item["process_number"]: item for item in api.get(ASSETS_URL, headers=nit).json()}

    esperado = {
        "BR 10 2023 000001-1": ("Patente da autora", "Patente", "2023-01-10", "Em exame", "Autora Teste", "autora@teste.edu.br"),
        "BR 51 2024 000002-2": ("Software de outro autor", "Programa de Computador", "2024-05-20", "Registrado", "Outro Autor", "outro@teste.edu.br"),
        "BR 10 2022 000003-3": ("Patente sem autor vinculado", "Patente", "2022-08-01", "Deferida", "Equipe", None),
    }
    assert por_processo.keys() == esperado.keys()
    for processo, (titulo, natureza, data, situacao, autores, email) in esperado.items():
        item = por_processo[processo]
        assert (item["title"], item["asset_type"], item["deposit_date"]) == (titulo, natureza, data)
        assert (item["status"], item["authors"], item["author_email"]) == (situacao, autores, email)


# ------------------------------------------------------------------ G5 — corrida no cadastro (linhas 49–52)


# G5 / US04 — CA04-5 — partição inválida (processo duplicado) chegando pelo caminho da corrida:
# a checagem prévia não enxerga o outro cadastro e quem barra é a restrição UNIQUE do banco.
def test_corrida_no_cadastro_do_mesmo_processo_retorna_409(
    api: TestClient, nit, assets, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simula a outra requisição: a consulta de duplicidade "não vê" o processo já gravado.
    monkeypatch.setattr(db_session, "scalar", lambda *args, **kwargs: None)
    response = _cadastrar(api, nit, process_number="BR 10 2023 000001-1")
    monkeypatch.undo()

    assert response.status_code == 409
    assert "BR 10 2023 000001-1" in response.json()["detail"]
    processos = [item["process_number"] for item in api.get(ASSETS_URL, headers=nit).json()]
    assert processos.count("BR 10 2023 000001-1") == 1
    assert len(processos) == len(assets)


# ------------------------------------------------------------------ G6 — oráculo pelo comportamento


# G6 / US01 — CA01-1 — critério de aceitação: o token emitido identifica o usuário e o perfil (comportamento,
# não estrutura interna do JWT)
@pytest.mark.parametrize(("email", "perfil"), [("nit@teste.edu.br", "NIT"), ("autora@teste.edu.br", "AUTOR")])
def test_token_do_login_identifica_usuario_e_perfil(api: TestClient, users, email: str, perfil: str) -> None:
    login = api.post("/api/auth/login", json={"email": email, "password": "senha-teste-123"}).json()

    me = api.get(ME_URL, headers={"Authorization": f"Bearer {login['access_token']}"})

    assert me.status_code == 200
    assert me.json() == login["user"]
    assert me.json()["role"] == perfil
