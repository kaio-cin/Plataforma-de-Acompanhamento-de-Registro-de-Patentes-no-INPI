from datetime import date, timedelta

import pytest
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Asset, AssetType, Dispatch, RpiEdition, User
from app.services.alert_service import create_alerts_for
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


# --- Edição (US05) ----------------------------------------------------------

NIT = "nit@teste.edu.br"
AUTORA = "autora@teste.edu.br"
OUTRO_AUTOR = "outro@teste.edu.br"
TITULO_NOVO = "Título alterado na edição"

# Corpo completo para editar assets[0] ("Patente da autora"): só o título muda.
EDICAO = {
    "title": TITULO_NOVO,
    "asset_type": "Patente",
    "process_number": "BR 10 2023 000001-1",
    "deposit_date": "2023-01-10",
    "status": "Em exame",
    "authors": "Autora Teste",
    "author_email": AUTORA,
}


def _corpo(**mudancas: object) -> dict[str, object]:
    return {**EDICAO, **mudancas}


def _gravado(db_session: Session, asset_id: int) -> dict[str, object]:
    """Campos do ativo, conferindo o objeto da sessão e o que está no banco.

    Sem recarregar, pega uma alteração feita no objeto e não desfeita; recarregando, pega o que foi gravado.
    """

    def campos(ativo: Asset) -> dict[str, object]:
        return {
            "title": ativo.title,
            "asset_type": ativo.asset_type,
            "process_number": ativo.process_number,
            "deposit_date": ativo.deposit_date,
            "status": ativo.status,
            "authors": ativo.authors,
            "author_user_id": ativo.author_user_id,
        }

    na_sessao = campos(db_session.get(Asset, asset_id))
    db_session.expire_all()
    no_banco = campos(db_session.get(Asset, asset_id))
    assert na_sessao == no_banco
    return no_banco


def _titulos_visiveis(client: TestClient, email: str) -> list[str]:
    return [item["title"] for item in client.get("/api/assets/", headers=auth_header(client, email)).json()]


def _ativo_antigo(db_session: Session, process_number: str, title: str = "Ativo antigo") -> Asset:
    """Ativo gravado direto no banco, sem passar pelas regras do cadastro."""
    ativo = Asset(
        title=title,
        asset_type=AssetType.PATENTE,
        process_number=process_number,
        deposit_date=date(2020, 6, 1),
        status="Em exame",
        authors="Equipe",
    )
    db_session.add(ativo)
    db_session.commit()
    return ativo


def _com_despacho(db_session: Session, ativo: Asset) -> None:
    edition = RpiEdition(number=2900, publication_date=date(2026, 11, 24))
    db_session.add(
        Dispatch(
            edition=edition,
            asset=ativo,
            process_number=ativo.process_number,
            code="6.1",
            description="Exigência técnica",
            publication_date=edition.publication_date,
        )
    )
    db_session.commit()


def test_edicao_nit_altera_todos_os_campos(client: TestClient, db_session: Session, assets, users) -> None:
    ativo = assets[0]
    corpo = {
        "title": "  Patente   revisada  ",
        "asset_type": "Programa de Computador",
        "process_number": "br 51  2025   000777-7",
        "deposit_date": "2024-12-01",
        "status": "Concedida",
        "authors": "Autora Teste,  Coautor Novo",
        "author_email": OUTRO_AUTOR,
    }
    headers = auth_header(client, NIT)

    response = client.put(f"/api/assets/{ativo.id}", json=corpo, headers=headers)

    assert response.status_code == 200
    esperado = {
        "id": ativo.id,
        "title": "Patente revisada",
        "asset_type": "Programa de Computador",
        "process_number": "BR 51 2025 000777-7",
        "deposit_date": "2024-12-01",
        "status": "Concedida",
        "authors": "Autora Teste, Coautor Novo",
        "author_user_id": users["outro_autor"].id,
        "author_email": OUTRO_AUTOR,
    }
    assert response.json() == esperado
    assert client.get(f"/api/assets/{ativo.id}", headers=headers).json() == esperado


def test_edicao_autor_no_proprio_ativo_retorna_403(client: TestClient, db_session: Session, assets) -> None:
    antes = _gravado(db_session, assets[0].id)

    response = client.put(f"/api/assets/{assets[0].id}", json=_corpo(), headers=auth_header(client, AUTORA))

    assert response.status_code == 403
    assert _gravado(db_session, assets[0].id) == antes


def test_edicao_sem_login_retorna_401(client: TestClient, db_session: Session, assets) -> None:
    antes = _gravado(db_session, assets[0].id)

    assert client.put(f"/api/assets/{assets[0].id}", json=_corpo()).status_code == 401
    assert _gravado(db_session, assets[0].id) == antes


def test_edicao_de_id_inexistente_retorna_404(client: TestClient, assets) -> None:
    response = client.put(f"/api/assets/{ID_INEXISTENTE}", json=_corpo(), headers=auth_header(client, NIT))

    assert response.status_code == 404
    assert response.json() == {"detail": "Ativo não encontrado."}


def test_edicao_sem_author_email_retorna_422_e_mantem_o_vinculo(
    client: TestClient, db_session: Session, assets, users
) -> None:
    corpo = _corpo()
    del corpo["author_email"]
    antes = _gravado(db_session, assets[0].id)

    response = client.put(f"/api/assets/{assets[0].id}", json=corpo, headers=auth_header(client, NIT))

    assert response.status_code == 422
    assert _gravado(db_session, assets[0].id) == antes
    assert antes["author_user_id"] == users["autora"].id


@pytest.mark.parametrize("email", [None, ""], ids=["null", "vazio"])
def test_edicao_author_email_null_ou_vazio_remove_o_vinculo(
    client: TestClient, db_session: Session, assets, email: str | None
) -> None:
    response = client.put(
        f"/api/assets/{assets[0].id}", json=_corpo(author_email=email), headers=auth_header(client, NIT)
    )

    assert response.status_code == 200
    assert response.json()["author_user_id"] is None
    assert response.json()["author_email"] is None
    assert _gravado(db_session, assets[0].id)["author_user_id"] is None
    assert _titulos_visiveis(client, AUTORA) == []


def test_edicao_troca_de_autor(client: TestClient, assets, users) -> None:
    response = client.put(
        f"/api/assets/{assets[0].id}", json=_corpo(author_email=OUTRO_AUTOR), headers=auth_header(client, NIT)
    )

    assert response.status_code == 200
    assert response.json()["author_user_id"] == users["outro_autor"].id
    assert response.json()["author_email"] == OUTRO_AUTOR
    assert TITULO_NOVO in _titulos_visiveis(client, OUTRO_AUTOR)
    assert _titulos_visiveis(client, AUTORA) == []


def test_edicao_mantendo_o_mesmo_autor(client: TestClient, assets, users) -> None:
    response = client.put(f"/api/assets/{assets[0].id}", json=_corpo(), headers=auth_header(client, NIT))

    assert response.status_code == 200
    assert response.json()["title"] == TITULO_NOVO
    assert response.json()["author_user_id"] == users["autora"].id
    assert _titulos_visiveis(client, AUTORA) == [TITULO_NOVO]


@pytest.mark.parametrize("email", ["naoexiste@teste.edu.br", NIT], ids=["inexistente", "usuario_nit"])
def test_edicao_com_autor_invalido_retorna_422(client: TestClient, db_session: Session, assets, email: str) -> None:
    antes = _gravado(db_session, assets[0].id)

    response = client.put(
        f"/api/assets/{assets[0].id}", json=_corpo(author_email=email), headers=auth_header(client, NIT)
    )

    assert response.status_code == 422
    assert email in response.json()["detail"]
    assert _gravado(db_session, assets[0].id) == antes


@pytest.mark.parametrize(
    ("numero", "gravado"),
    [("BR 10 2023 000001-1", "BR 10 2023 000001-1"), ("br10.2023.000001-1", "BR10.2023.000001-1")],
    ids=["igual", "outra_formatacao"],
)
def test_edicao_mantendo_o_proprio_numero(client: TestClient, assets, numero: str, gravado: str) -> None:
    response = client.put(
        f"/api/assets/{assets[0].id}", json=_corpo(process_number=numero), headers=auth_header(client, NIT)
    )

    assert response.status_code == 200
    assert response.json()["process_number"] == gravado


@pytest.mark.parametrize("numero", ["BR 51 2024 000002-2", "BR51.2024.000002-2"], ids=["igual", "outra_formatacao"])
def test_edicao_com_numero_de_outro_ativo_retorna_409(
    client: TestClient, db_session: Session, assets, numero: str
) -> None:
    antes = _gravado(db_session, assets[0].id)

    response = client.put(
        f"/api/assets/{assets[0].id}", json=_corpo(process_number=numero), headers=auth_header(client, NIT)
    )

    assert response.status_code == 409
    assert response.json() == {"detail": f"Já existe um ativo cadastrado com o processo {numero}."}
    assert _gravado(db_session, assets[0].id) == antes


def test_edicao_de_ativos_antigos_gemeos(client: TestClient, db_session: Session, users) -> None:
    # Dois ativos antigos com o mesmo número normalizado, gravados antes da checagem normalizada.
    primeiro = _ativo_antigo(db_session, "BR 10 2020 000050-5", title="Primeiro gêmeo")
    _ativo_antigo(db_session, "BR10.2020.000050-5", title="Segundo gêmeo")
    headers = auth_header(client, NIT)
    corpo = {
        "title": "Primeiro gêmeo revisado",
        "asset_type": "Patente",
        "process_number": "BR 10 2020 000050-5",
        "deposit_date": "2020-06-01",
        "status": "Em exame",
        "authors": "Equipe",
        "author_email": None,
    }

    so_titulo = client.put(f"/api/assets/{primeiro.id}", json=corpo, headers=headers)

    assert so_titulo.status_code == 200
    assert so_titulo.json()["title"] == "Primeiro gêmeo revisado"

    antes = _gravado(db_session, primeiro.id)
    igual_ao_outro = client.put(
        f"/api/assets/{primeiro.id}",
        json={**corpo, "title": "Não deve ser gravado", "process_number": "BR10.2020.000050-5"},
        headers=headers,
    )

    assert igual_ao_outro.status_code == 409
    assert igual_ao_outro.json() == {"detail": "Já existe um ativo cadastrado com o processo BR10.2020.000050-5."}
    assert _gravado(db_session, primeiro.id) == antes


@pytest.mark.parametrize(
    "mudanca",
    [
        {"deposit_date": (date.today() + timedelta(days=1)).isoformat()},
        {"asset_type": "Marca"},
        {"status": None},
    ],
    ids=["data_no_futuro", "natureza_invalida", "campo_obrigatorio_ausente"],
)
def test_edicao_com_dados_invalidos_retorna_422(
    client: TestClient, db_session: Session, assets, mudanca: dict[str, object]
) -> None:
    corpo = _corpo(**mudanca)
    if corpo["status"] is None:
        del corpo["status"]
    antes = _gravado(db_session, assets[0].id)

    response = client.put(f"/api/assets/{assets[0].id}", json=corpo, headers=auth_header(client, NIT))

    assert response.status_code == 422
    assert _gravado(db_session, assets[0].id) == antes


def test_edicao_com_despacho_bloqueia_troca_do_numero(client: TestClient, db_session: Session, assets) -> None:
    _com_despacho(db_session, assets[0])
    antes = _gravado(db_session, assets[0].id)

    response = client.put(
        f"/api/assets/{assets[0].id}",
        json=_corpo(process_number="BR 10 2023 000009-9"),
        headers=auth_header(client, NIT),
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Este ativo já tem despachos da RPI ligados ao processo BR 10 2023 000001-1; "
        "o número não pode ser trocado."
    }
    assert _gravado(db_session, assets[0].id) == antes


@pytest.mark.parametrize(
    "mudanca",
    [{"process_number": "BR10.2023.000001-1"}, {"asset_type": "Programa de Computador"}],
    ids=["so_formatacao", "natureza"],
)
def test_edicao_com_despacho_permite_formatacao_e_natureza(
    client: TestClient, db_session: Session, assets, mudanca: dict[str, object]
) -> None:
    _com_despacho(db_session, assets[0])

    response = client.put(f"/api/assets/{assets[0].id}", json=_corpo(**mudanca), headers=auth_header(client, NIT))

    assert response.status_code == 200
    for campo, valor in mudanca.items():
        assert response.json()[campo] == valor


def test_edicao_corrige_ativo_antigo_fora_das_regras(client: TestClient, db_session: Session, users) -> None:
    antigo = _ativo_antigo(db_session, "BR1", title="X")
    corpo = {
        "title": "Título corrigido",
        "asset_type": "Patente",
        "process_number": "BR 10 2010 000077-7",
        "deposit_date": "2010-01-01",
        "status": "Em exame",
        "authors": "Equipe",
        "author_email": None,
    }

    response = client.put(f"/api/assets/{antigo.id}", json=corpo, headers=auth_header(client, NIT))

    assert response.status_code == 200
    assert response.json()["title"] == "Título corrigido"
    assert response.json()["process_number"] == "BR 10 2010 000077-7"


def test_edicao_com_integrity_error_no_commit_retorna_409(
    client: TestClient, db_session: Session, assets, monkeypatch: pytest.MonkeyPatch
) -> None:
    antes = _gravado(db_session, assets[0].id)
    headers = auth_header(client, NIT)

    def commit_com_corrida() -> None:
        # Simula outra requisição gravando o mesmo número entre a checagem e o commit.
        raise IntegrityError("UPDATE assets", {}, Exception("UNIQUE constraint failed: assets.process_number"))

    monkeypatch.setattr(db_session, "commit", commit_com_corrida)

    response = client.put(f"/api/assets/{assets[0].id}", json=_corpo(), headers=headers)

    assert response.status_code == 409
    assert response.json() == {"detail": "Já existe um ativo cadastrado com o processo BR 10 2023 000001-1."}
    assert _gravado(db_session, assets[0].id) == antes


# --- Edição e alertas do autor desvinculado (US05) --------------------------


def _despacho_com_alertas(db_session: Session, ativo: Asset, numero_edicao: int) -> Dispatch:
    """Despacho do ativo numa edição nova, já com os alertas do NIT e do autor vinculado."""
    edition = RpiEdition(number=numero_edicao, publication_date=date(2026, 11, 24))
    dispatch = Dispatch(
        edition=edition,
        asset=ativo,
        process_number=ativo.process_number,
        code="6.1",
        description="Exigência técnica",
        publication_date=edition.publication_date,
    )
    db_session.add(dispatch)
    create_alerts_for(db_session, dispatch)
    db_session.commit()
    return dispatch


def _alertas_por_ativo(client: TestClient, email: str) -> list[int]:
    """asset_id de cada alerta do usuário, como a rota de alertas devolve."""
    return sorted(item["asset_id"] for item in client.get("/api/alerts/", headers=auth_header(client, email)).json())


def _nao_lidos(client: TestClient, email: str) -> int:
    return client.get("/api/alerts/unread-count", headers=auth_header(client, email)).json()["count"]


def test_edicao_alertas_troca_de_autor_remove_so_os_do_antigo_no_ativo(
    client: TestClient, db_session: Session, assets, users
) -> None:
    # A autora também está vinculada a assets[2], para ter alertas em outro ativo.
    assets[2].author_user = users["autora"]
    db_session.commit()
    _despacho_com_alertas(db_session, assets[0], 2901)
    _despacho_com_alertas(db_session, assets[2], 2902)
    assert _alertas_por_ativo(client, AUTORA) == sorted([assets[0].id, assets[2].id])
    assert _nao_lidos(client, AUTORA) == 2

    response = client.put(
        f"/api/assets/{assets[0].id}", json=_corpo(author_email=OUTRO_AUTOR), headers=auth_header(client, NIT)
    )

    assert response.status_code == 200
    assert _alertas_por_ativo(client, AUTORA) == [assets[2].id]
    assert _nao_lidos(client, AUTORA) == 1
    assert _alertas_por_ativo(client, NIT) == sorted([assets[0].id, assets[2].id])
    assert _alertas_por_ativo(client, OUTRO_AUTOR) == []


@pytest.mark.parametrize("email", [None, ""], ids=["null", "vazio"])
def test_edicao_alertas_remocao_do_autor_remove_os_dele(
    client: TestClient, db_session: Session, assets, email: str | None
) -> None:
    _despacho_com_alertas(db_session, assets[0], 2901)

    response = client.put(
        f"/api/assets/{assets[0].id}", json=_corpo(author_email=email), headers=auth_header(client, NIT)
    )

    assert response.status_code == 200
    assert _alertas_por_ativo(client, AUTORA) == []
    assert _nao_lidos(client, AUTORA) == 0
    assert _alertas_por_ativo(client, NIT) == [assets[0].id]


def test_edicao_alertas_mesmo_autor_mantem_os_alertas_e_a_leitura(
    client: TestClient, db_session: Session, assets
) -> None:
    _despacho_com_alertas(db_session, assets[0], 2901)
    _despacho_com_alertas(db_session, assets[0], 2902)
    headers_autora = auth_header(client, AUTORA)
    primeiro = client.get("/api/alerts/", headers=headers_autora).json()[0]["id"]
    assert client.patch(f"/api/alerts/{primeiro}/read", headers=headers_autora).status_code == 200
    antes = {item["id"]: item["is_read"] for item in client.get("/api/alerts/", headers=headers_autora).json()}

    response = client.put(f"/api/assets/{assets[0].id}", json=_corpo(), headers=auth_header(client, NIT))

    assert response.status_code == 200
    depois = {item["id"]: item["is_read"] for item in client.get("/api/alerts/", headers=headers_autora).json()}
    assert depois == antes
    assert sorted(antes.values()) == [False, True]
    assert _nao_lidos(client, AUTORA) == 1


@pytest.mark.parametrize("email", [AUTORA, None], ids=["troca", "remocao"])
def test_edicao_alertas_autor_antigo_com_perfil_nit_nao_perde_alertas(
    client: TestClient, db_session: Session, assets, users, email: str | None
) -> None:
    # Dado antigo: um usuário NIT gravado direto como autor vinculado.
    assets[2].author_user = users["nit"]
    db_session.commit()
    _despacho_com_alertas(db_session, assets[2], 2901)
    corpo = {
        "title": "Patente sem autor vinculado",
        "asset_type": "Patente",
        "process_number": "BR 10 2022 000003-3",
        "deposit_date": "2022-08-01",
        "status": "Deferida",
        "authors": "Equipe",
        "author_email": email,
    }

    response = client.put(f"/api/assets/{assets[2].id}", json=corpo, headers=auth_header(client, NIT))

    assert response.status_code == 200
    assert _alertas_por_ativo(client, NIT) == [assets[2].id]
    assert _nao_lidos(client, NIT) == 1


@pytest.mark.parametrize(
    ("mudanca", "status_esperado"),
    [
        ({"process_number": "BR 51 2024 000002-2"}, 409),
        ({"process_number": "BR 10 2023 000009-9"}, 409),
        ({"author_email": "naoexiste@teste.edu.br"}, 422),
        ({"deposit_date": (date.today() + timedelta(days=1)).isoformat()}, 422),
    ],
    ids=["duplicado", "bloqueado_por_despacho", "autor_inexistente", "data_no_futuro"],
)
def test_edicao_alertas_put_que_falha_mantem_os_alertas(
    client: TestClient, db_session: Session, assets, users, mudanca: dict[str, object], status_esperado: int
) -> None:
    _despacho_com_alertas(db_session, assets[0], 2901)
    # Todos tentam trocar o autor; o autor_inexistente troca para um e-mail que não existe.
    corpo = _corpo(**{"author_email": OUTRO_AUTOR, **mudanca})

    response = client.put(f"/api/assets/{assets[0].id}", json=corpo, headers=auth_header(client, NIT))

    assert response.status_code == status_esperado
    assert _gravado(db_session, assets[0].id)["author_user_id"] == users["autora"].id
    assert _alertas_por_ativo(client, AUTORA) == [assets[0].id]
    assert _nao_lidos(client, AUTORA) == 1


def test_edicao_alertas_falha_real_no_commit_mantem_vinculo_e_alertas(
    client: TestClient, db_session: Session, users
) -> None:
    # Gêmeos antigos: mudar o primeiro para o formato exato do segundo só falha no UNIQUE do banco,
    # depois que os alertas da autora já foram apagados na transação.
    primeiro = _ativo_antigo(db_session, "BR 10 2020 000050-5", title="Primeiro gêmeo")
    _ativo_antigo(db_session, "BR10.2020.000050-5", title="Segundo gêmeo")
    primeiro.author_user = users["autora"]
    db_session.commit()
    _despacho_com_alertas(db_session, primeiro, 2901)
    corpo = {
        "title": "Não deve ser gravado",
        "asset_type": "Patente",
        "process_number": "BR10.2020.000050-5",
        "deposit_date": "2020-06-01",
        "status": "Em exame",
        "authors": "Equipe",
        "author_email": OUTRO_AUTOR,
    }

    response = client.put(f"/api/assets/{primeiro.id}", json=corpo, headers=auth_header(client, NIT))

    assert response.status_code == 409
    gravado = _gravado(db_session, primeiro.id)
    assert gravado["author_user_id"] == users["autora"].id
    assert gravado["title"] == "Primeiro gêmeo"
    assert _alertas_por_ativo(client, AUTORA) == [primeiro.id]
    assert _alertas_por_ativo(client, OUTRO_AUTOR) == []
