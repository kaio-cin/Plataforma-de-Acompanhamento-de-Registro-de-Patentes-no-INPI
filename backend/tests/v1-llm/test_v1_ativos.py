"""Testes de ativos — US04 (cadastro), US06 (listagem) e US07 (vínculo de autor).

Técnicas: critérios de aceitação (CA), partições de equivalência (PE) e análise de
valores-limite (AVL) sobre cada campo do cadastro.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_header

ASSETS_URL = "/api/assets/"

ATIVO_VALIDO = {
    "title": "Método de compostagem acelerada",
    "asset_type": "Patente",
    "process_number": "BR 10 2025 000999-9",
    "deposit_date": "2025-02-14",
    "status": "Em análise",
    "authors": "Fulano de Tal, Beltrana Souza",
}


@pytest.fixture
def nit_headers(client: TestClient, users) -> dict[str, str]:
    return auth_header(client, "nit@teste.edu.br")


def _cadastrar(client: TestClient, headers: dict[str, str], **campos):
    return client.post(ASSETS_URL, json={**ATIVO_VALIDO, **campos}, headers=headers)


# ---------------------------------------------------------------- US04 — cadastro


# US04 / CA04-1 — critério de aceitação: cadastro válido retorna 201 com os dados
def test_cadastro_valido_retorna_201_com_dados(client: TestClient, nit_headers) -> None:
    response = _cadastrar(client, nit_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    for campo in ("title", "asset_type", "process_number", "deposit_date", "status", "authors"):
        assert body[campo] == ATIVO_VALIDO[campo]
    assert body["author_email"] is None


# US04 / CA04-1 — critério de aceitação: ativo cadastrado passa a constar na listagem
def test_ativo_cadastrado_aparece_na_listagem(client: TestClient, nit_headers) -> None:
    _cadastrar(client, nit_headers)

    response = client.get(ASSETS_URL, headers=nit_headers)
    assert ATIVO_VALIDO["process_number"] in [item["process_number"] for item in response.json()]


# US04 / CA04-2 — PE válida: as duas naturezas aceitas
@pytest.mark.parametrize("natureza", ["Patente", "Programa de Computador"])
def test_naturezas_validas_sao_aceitas(client: TestClient, nit_headers, natureza: str) -> None:
    response = _cadastrar(client, nit_headers, asset_type=natureza)

    assert response.status_code == 201
    assert response.json()["asset_type"] == natureza


# US04 / CA04-2 — PE inválida: qualquer outra natureza
@pytest.mark.parametrize("natureza", ["Marca", "patente", "Desenho Industrial", ""])
def test_natureza_invalida_retorna_422(client: TestClient, nit_headers, natureza: str) -> None:
    response = _cadastrar(client, nit_headers, asset_type=natureza)

    assert response.status_code == 422


# US04 / CA04-3 — AVL no título: 2 (inválido), 3 (válido), 500 (válido), 501 (inválido)
@pytest.mark.parametrize(
    ("tamanho", "status_esperado"),
    [(2, 422), (3, 201), (500, 201), (501, 422)],
)
def test_limites_de_tamanho_do_titulo(client: TestClient, nit_headers, tamanho: int, status_esperado: int) -> None:
    response = _cadastrar(client, nit_headers, title="T" * tamanho)

    assert response.status_code == status_esperado


# US04 / CA04-3 — PE válida: espaços extras no título são normalizados
def test_titulo_tem_espacos_normalizados(client: TestClient, nit_headers) -> None:
    response = _cadastrar(client, nit_headers, title="  Método   de    compostagem  ")

    assert response.status_code == 201
    assert response.json()["title"] == "Método de compostagem"


# US04 / CA04-3 — AVL: título que só atinge 3 caracteres por causa de espaços não é válido
def test_titulo_com_menos_de_3_caracteres_efetivos_retorna_422(client: TestClient, nit_headers) -> None:
    response = _cadastrar(client, nit_headers, title=" ab ")

    assert response.status_code == 422


# US04 / CA04-4 — AVL no número do processo: 4, 5, 50 e 51 caracteres
@pytest.mark.parametrize(
    ("tamanho", "status_esperado"),
    [(4, 422), (5, 201), (50, 201), (51, 422)],
)
def test_limites_de_tamanho_do_processo(client: TestClient, nit_headers, tamanho: int, status_esperado: int) -> None:
    response = _cadastrar(client, nit_headers, process_number="9" * tamanho)

    assert response.status_code == status_esperado


# US04 / CA04-4 — PE válida: número do processo é normalizado (maiúsculas e espaços simples)
def test_numero_do_processo_e_normalizado(client: TestClient, nit_headers) -> None:
    response = _cadastrar(client, nit_headers, process_number="  br 10  2025   000999-9 ")

    assert response.status_code == 201
    assert response.json()["process_number"] == "BR 10 2025 000999-9"


# US04 / CA04-5 — PE inválida: processo já cadastrado
def test_processo_duplicado_retorna_409(client: TestClient, assets, nit_headers) -> None:
    response = _cadastrar(client, nit_headers, process_number="BR 10 2023 000001-1")

    assert response.status_code == 409
    assert "BR 10 2023 000001-1" in response.json()["detail"]


# US04 / CA04-5 — PE inválida: duplicado que só difere por caixa e espaços
def test_processo_duplicado_apos_normalizacao_retorna_409(client: TestClient, assets, nit_headers) -> None:
    response = _cadastrar(client, nit_headers, process_number="br 10   2023 000001-1")

    assert response.status_code == 409


# US04 / CA04-6 — AVL na data de depósito: hoje é aceito
def test_data_de_deposito_hoje_e_aceita(client: TestClient, nit_headers) -> None:
    response = _cadastrar(client, nit_headers, deposit_date=date.today().isoformat())

    assert response.status_code == 201


# US04 / CA04-6 — AVL na data de depósito: amanhã é recusado
def test_data_de_deposito_amanha_retorna_422(client: TestClient, nit_headers) -> None:
    amanha = (date.today() + timedelta(days=1)).isoformat()
    response = _cadastrar(client, nit_headers, deposit_date=amanha)

    assert response.status_code == 422


# US04 / CA04-6 — PE inválida: data inexistente ou em formato errado
@pytest.mark.parametrize("data", ["2023-02-30", "12/03/2023", "ontem"])
def test_data_de_deposito_invalida_retorna_422(client: TestClient, nit_headers, data: str) -> None:
    response = _cadastrar(client, nit_headers, deposit_date=data)

    assert response.status_code == 422


# US04 / CA04-7 — AVL na situação: 1, 2, 100 e 101 caracteres
@pytest.mark.parametrize(
    ("tamanho", "status_esperado"),
    [(1, 422), (2, 201), (100, 201), (101, 422)],
)
def test_limites_de_tamanho_da_situacao(client: TestClient, nit_headers, tamanho: int, status_esperado: int) -> None:
    response = _cadastrar(client, nit_headers, status="S" * tamanho)

    assert response.status_code == status_esperado


# US04 / CA04-8 — AVL nos autores: 1, 2, 1000 e 1001 caracteres
@pytest.mark.parametrize(
    ("tamanho", "status_esperado"),
    [(1, 422), (2, 201), (1000, 201), (1001, 422)],
)
def test_limites_de_tamanho_dos_autores(client: TestClient, nit_headers, tamanho: int, status_esperado: int) -> None:
    response = _cadastrar(client, nit_headers, authors="A" * tamanho)

    assert response.status_code == status_esperado


# US04 / CA04-9 — PE inválida: cada campo obrigatório ausente
@pytest.mark.parametrize("campo", ["title", "asset_type", "process_number", "deposit_date", "status", "authors"])
def test_campo_obrigatorio_ausente_retorna_422(client: TestClient, nit_headers, campo: str) -> None:
    payload = {chave: valor for chave, valor in ATIVO_VALIDO.items() if chave != campo}
    response = client.post(ASSETS_URL, json=payload, headers=nit_headers)

    assert response.status_code == 422


# ---------------------------------------------------------------- US06 — listagem


# US06 / CA06-1 — critério de aceitação: NIT vê todos os ativos, com ou sem autor
def test_nit_ve_todos_os_ativos(client: TestClient, assets, nit_headers) -> None:
    response = client.get(ASSETS_URL, headers=nit_headers)

    assert response.status_code == 200
    assert len(response.json()) == len(assets)


# US06 / CA06-2 — critério de aceitação: ordenação por data de depósito decrescente
def test_listagem_ordenada_por_data_de_deposito_decrescente(client: TestClient, assets, nit_headers) -> None:
    response = client.get(ASSETS_URL, headers=nit_headers)

    datas = [item["deposit_date"] for item in response.json()]
    assert datas == sorted(datas, reverse=True)


# US06 / CA06-3 — critério de aceitação: cada item traz os campos e o status atual
def test_itens_da_listagem_trazem_campos_esperados(client: TestClient, assets, nit_headers) -> None:
    response = client.get(ASSETS_URL, headers=nit_headers)

    campos = {"id", "title", "asset_type", "process_number", "deposit_date", "status", "authors", "author_email"}
    for item in response.json():
        assert campos <= item.keys()
        assert item["status"]


# US06 / CA06-4 — PE: carteira vazia
def test_carteira_vazia_retorna_lista_vazia(client: TestClient, nit_headers) -> None:
    response = client.get(ASSETS_URL, headers=nit_headers)

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------- US07 — vínculo de autor


# US07 / CA07-1 — critério de aceitação + PE válida (e-mail de AUTOR cadastrado)
def test_vincular_autor_existente(client: TestClient, nit_headers, users) -> None:
    response = _cadastrar(client, nit_headers, author_email="autora@teste.edu.br")

    assert response.status_code == 201
    assert response.json()["author_email"] == "autora@teste.edu.br"
    assert response.json()["author_user_id"] == users["autora"].id

    lista_autora = client.get(ASSETS_URL, headers=auth_header(client, "autora@teste.edu.br")).json()
    assert [item["process_number"] for item in lista_autora] == [ATIVO_VALIDO["process_number"]]


# US07 / CA07-1 — o outro autor não passa a ver o ativo vinculado à autora
def test_ativo_vinculado_nao_aparece_para_outro_autor(client: TestClient, nit_headers) -> None:
    _cadastrar(client, nit_headers, author_email="autora@teste.edu.br")

    lista_outro = client.get(ASSETS_URL, headers=auth_header(client, "outro@teste.edu.br")).json()
    assert lista_outro == []


# US07 / CA07-2 — PE inválida: e-mail não cadastrado; o ativo não é gravado
def test_vincular_email_inexistente_retorna_422_e_nao_grava(client: TestClient, nit_headers) -> None:
    response = _cadastrar(client, nit_headers, author_email="naoexiste@teste.edu.br")

    assert response.status_code == 422
    assert client.get(ASSETS_URL, headers=nit_headers).json() == []


# US07 / CA07-3 — PE inválida: e-mail de usuário NIT
def test_vincular_usuario_nit_como_autor_retorna_422(client: TestClient, nit_headers) -> None:
    response = _cadastrar(client, nit_headers, author_email="nit@teste.edu.br")

    assert response.status_code == 422


# US07 / CA07-4 — PE válida: e-mail ausente, vazio ou só com espaços => sem vínculo
@pytest.mark.parametrize("valor", [None, "", "   "])
def test_email_de_autor_vazio_cria_sem_vinculo(client: TestClient, nit_headers, valor) -> None:
    response = _cadastrar(client, nit_headers, author_email=valor)

    assert response.status_code == 201
    assert response.json()["author_email"] is None
    assert response.json()["author_user_id"] is None


# US07 / CA07-5 — PE válida: e-mail do autor com maiúsculas
def test_vincular_autor_com_email_em_maiusculas(client: TestClient, nit_headers, users) -> None:
    response = _cadastrar(client, nit_headers, author_email="AUTORA@TESTE.EDU.BR")

    assert response.status_code == 201
    assert response.json()["author_user_id"] == users["autora"].id


# US07 / CA07-6 — PE inválida: formato de e-mail inválido
@pytest.mark.parametrize("email", ["nao-e-email", "autora@", "autora teste@teste.edu.br"])
def test_email_de_autor_malformado_retorna_422(client: TestClient, nit_headers, email: str) -> None:
    response = _cadastrar(client, nit_headers, author_email=email)

    assert response.status_code == 422
