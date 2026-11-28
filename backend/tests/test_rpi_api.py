"""Rotas da RPI: "Processar agora" (US08) e lista de edições (US10).

Sem internet e sem banco real: o download devolve os XML das fixtures, send_email é falso e os
e-mails depois da resposta usam a fábrica de sessões do banco em memória (override no conftest).
"""

import urllib.request
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alert, Asset, AssetType, Dispatch, RpiEdition, RpiEditionStatus, User
from app.services import email_service, rpi_download_service, rpi_job_service, rpi_processing_service
from app.services.rpi_errors import (
    RpiAlreadyProcessingError,
    RpiDownloadError,
    RpiInvalidFileError,
    RpiNotPublishedError,
    RpiParseError,
    RpiProcessingError,
)
from tests.conftest import auth_header

FIXTURES = Path(__file__).parent / "fixtures" / "rpi"
PATENTE_6_1 = "BR 11 2021 007863-0"  # na fixture 2916: despachos 6.1 e 15.11 (patentes)
URL_PROCESSAR = "/api/rpi/process"
URL_EDICOES = "/api/rpi/editions"


@pytest.fixture(autouse=True)
def sem_internet(monkeypatch: pytest.MonkeyPatch) -> None:
    def urlopen(*_args, **_kwargs):
        raise AssertionError("o teste tentou acessar a internet")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


@pytest.fixture(autouse=True)
def download_das_fixtures(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, bool]]:
    """O download devolve os XML da RPI 2916 das fixtures, sem gravar nada no disco."""
    chamadas: list[tuple[int, bool]] = []

    def download_edition(number: int, _data_dir=None, *, force: bool = False):
        chamadas.append((number, force))
        if number != 2916:
            raise RpiNotPublishedError(f"A RPI {number} ainda não foi publicada pelo INPI.")
        return {
            AssetType.PATENTE: FIXTURES / "patentes_2916.xml",
            AssetType.PROGRAMA_DE_COMPUTADOR: FIXTURES / "programas_2916.xml",
        }

    monkeypatch.setattr(rpi_download_service, "download_edition", download_edition)
    return chamadas


@pytest.fixture(autouse=True)
def enviados(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    destinatarios: list[str] = []

    def send_email(to: str, _subject: str, _body: str) -> bool:
        destinatarios.append(to)
        return True

    monkeypatch.setattr(email_service, "send_email", send_email)
    return destinatarios


@pytest.fixture
def ativo_na_rpi(db_session: Session, users: dict[str, User]) -> Asset:
    ativo = Asset(
        title="Patente com despachos na RPI 2916",
        asset_type=AssetType.PATENTE,
        process_number=PATENTE_6_1,
        deposit_date=date(2021, 1, 1),
        status="Em exame",
        authors="Autora Teste",
        author_user=users["autora"],
    )
    db_session.add(ativo)
    db_session.commit()
    return ativo


@pytest.fixture
def nit(client: TestClient, users: dict[str, User]) -> dict[str, str]:
    return auth_header(client, users["nit"].email)


@pytest.fixture
def hoje_2916(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quarta 25/11/2026: a edição esperada é a 2916."""
    monkeypatch.setattr(rpi_job_service, "today_in_brazil", lambda: date(2026, 11, 25))


def _falha_no_processamento(monkeypatch: pytest.MonkeyPatch, erro: Exception) -> None:
    def process_edition(*_args, **_kwargs):
        raise erro

    monkeypatch.setattr(rpi_processing_service, "process_edition", process_edition)


# --- POST /rpi/process: sucesso --------------------------------------------------------------------------------------


def test_processa_a_edicao_pedida(client: TestClient, nit: dict[str, str], ativo_na_rpi: Asset) -> None:
    response = client.post(URL_PROCESSAR, json={"number": 2916}, headers=nit)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "edition",
        "total_in_rpi",
        "skipped_by_parser",
        "matched",
        "new_dispatches",
        "existing_dispatches",
        "alerts_created",
        "unknown_codes",
        "type_mismatches",
        "ambiguous_processes",
        "duplicates_in_rpi",
    }
    assert body["edition"]["number"] == 2916
    assert body["edition"]["publication_date"] == "2026-11-24"
    assert body["edition"]["status"] == "Processada"
    assert body["edition"]["error_message"] is None
    assert body["edition"]["processed_at"] is not None
    assert "file_path" not in body["edition"]
    assert body["new_dispatches"] == body["edition"]["dispatch_count"] == 2
    assert body["alerts_created"] == 4  # 2 despachos x (NIT + autora)
    assert body["total_in_rpi"] > body["matched"] == 2
    assert {"asset_type": "Patente", "code": "6.1", "count": 1} in body["unknown_codes"]


def test_emails_saem_depois_do_sucesso(
    client: TestClient, nit: dict[str, str], ativo_na_rpi: Asset, enviados: list[str], db_session: Session
) -> None:
    client.post(URL_PROCESSAR, json={"number": 2916}, headers=nit)

    assert sorted(enviados) == ["autora@teste.edu.br"] * 2 + ["nit@teste.edu.br"] * 2
    db_session.expire_all()
    assert all(db_session.scalars(select(Alert.email_sent)))


@pytest.mark.parametrize("corpo", [{}, {"number": None}, None])
def test_sem_numero_usa_a_edicao_esperada(
    client: TestClient, nit: dict[str, str], hoje_2916: None, download_das_fixtures, corpo
) -> None:
    if corpo is None:
        response = client.post(URL_PROCESSAR, headers=nit)
    else:
        response = client.post(URL_PROCESSAR, json=corpo, headers=nit)

    assert response.status_code == 200, response.text
    assert response.json()["edition"]["number"] == 2916
    assert download_das_fixtures == [(2916, False)]


def test_reprocessar_nao_duplica(
    client: TestClient, nit: dict[str, str], ativo_na_rpi: Asset, db_session: Session, enviados: list[str]
) -> None:
    primeira = client.post(URL_PROCESSAR, json={"number": 2916}, headers=nit).json()
    segunda = client.post(URL_PROCESSAR, json={"number": 2916}, headers=nit)

    assert segunda.status_code == 200
    body = segunda.json()
    assert body["new_dispatches"] == 0
    assert body["existing_dispatches"] == primeira["new_dispatches"]
    assert body["alerts_created"] == 0
    assert body["edition"]["id"] == primeira["edition"]["id"]
    assert db_session.scalar(select(func.count()).select_from(Dispatch)) == 2
    assert len(enviados) == 4  # nenhum e-mail repetido


def test_erro_de_leitura_baixa_de_novo(
    client: TestClient, nit: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[bool] = []
    original = rpi_processing_service.process_edition

    def process_edition(db, number, *, force_download=False, **kwargs):
        chamadas.append(force_download)
        if not force_download:
            raise RpiParseError("O arquivo de patentes da RPI 2916 não pôde ser lido.")
        return original(db, number, force_download=force_download, **kwargs)

    monkeypatch.setattr(rpi_processing_service, "process_edition", process_edition)

    response = client.post(URL_PROCESSAR, json={"number": 2916}, headers=nit)

    assert response.status_code == 200, response.text
    assert chamadas == [False, True]


# --- POST /rpi/process: erros ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("erro", "codigo"),
    [
        (RpiNotPublishedError("A RPI 2916 ainda não foi publicada pelo INPI."), 404),
        (RpiInvalidFileError("O arquivo de patentes da RPI 2916 não tem o formato esperado."), 502),
        (RpiDownloadError("Não foi possível baixar o arquivo de patentes da RPI 2916 após 3 tentativas."), 502),
        (RpiParseError("O arquivo de patentes da RPI 2916 não pôde ser lido."), 502),
        (RpiAlreadyProcessingError("A RPI 2916 já está sendo processada. Tente de novo em alguns minutos."), 409),
        (RpiProcessingError("Falha ao cruzar a RPI 2916 com os processos cadastrados. Tente processar de novo."), 500),
    ],
)
def test_erros_do_processamento(
    client: TestClient,
    nit: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    users: dict[str, User],
    assets: list[Asset],
    enviados: list[str],
    erro: Exception,
    codigo: int,
) -> None:
    # Um alerta com e-mail pendente: em caso de erro, a rota não agenda o envio.
    edicao = RpiEdition(number=2915, publication_date=date(2026, 11, 17), status=RpiEditionStatus.PROCESSADA)
    despacho = Dispatch(
        edition=edicao,
        asset=assets[0],
        process_number=assets[0].process_number,
        code="6.1",
        description="Exigência técnica",
        publication_date=edicao.publication_date,
    )
    db_session.add_all([edicao, despacho, Alert(user=users["nit"], dispatch=despacho)])
    db_session.commit()
    _falha_no_processamento(monkeypatch, erro)

    response = client.post(URL_PROCESSAR, json={"number": 2916}, headers=nit)

    assert response.status_code == codigo
    assert response.json() == {"detail": str(erro)}
    assert enviados == []


def test_nao_publicada_pelo_download(client: TestClient, nit: dict[str, str]) -> None:
    response = client.post(URL_PROCESSAR, json={"number": 2917}, headers=nit)

    assert response.status_code == 404
    assert response.json()["detail"] == "A RPI 2917 ainda não foi publicada pelo INPI."


@pytest.mark.parametrize("numero", [0, -1, 100000, "abc", 2916.5])
def test_numero_invalido(client: TestClient, nit: dict[str, str], download_das_fixtures, numero) -> None:
    response = client.post(URL_PROCESSAR, json={"number": numero}, headers=nit)

    assert response.status_code == 422
    assert download_das_fixtures == []


def test_numero_no_limite_e_aceito(client: TestClient, nit: dict[str, str]) -> None:
    # 99999 passa na validação; o INPI (falso) responde que não foi publicada.
    assert client.post(URL_PROCESSAR, json={"number": 99999}, headers=nit).status_code == 404


def test_processar_sem_login(client: TestClient, download_das_fixtures) -> None:
    assert client.post(URL_PROCESSAR, json={"number": 2916}).status_code == 401
    assert download_das_fixtures == []


def test_processar_com_perfil_autor(client: TestClient, users: dict[str, User], download_das_fixtures) -> None:
    autora = auth_header(client, users["autora"].email)

    response = client.post(URL_PROCESSAR, json={"number": 2916}, headers=autora)

    assert response.status_code == 403
    assert response.json()["detail"] == "Seu perfil não tem permissão para esta ação."
    assert download_das_fixtures == []


# --- GET /rpi/editions -----------------------------------------------------------------------------------------------


def test_lista_da_mais_nova_para_a_mais_antiga(client: TestClient, nit: dict[str, str], db_session: Session) -> None:
    db_session.add_all(
        [
            RpiEdition(number=2915, publication_date=date(2026, 11, 17), status=RpiEditionStatus.PROCESSADA,
                       dispatch_count=3, processed_at=datetime(2026, 11, 17, 12, 0), file_path="2915"),
            RpiEdition(number=2917, publication_date=date(2026, 12, 1), status=RpiEditionStatus.ERRO,
                       error_message="Não foi possível baixar o arquivo de patentes da RPI 2917 após 3 tentativas.",
                       processed_at=datetime(2026, 12, 1, 12, 0, 5)),
            RpiEdition(number=2916, publication_date=date(2026, 11, 24)),
        ]
    )
    db_session.commit()

    response = client.get(URL_EDICOES, headers=nit)

    assert response.status_code == 200
    body = response.json()
    assert [e["number"] for e in body] == [2917, 2916, 2915]
    assert body[0] == {
        "id": body[0]["id"],
        "number": 2917,
        "publication_date": "2026-12-01",
        "status": "Erro",
        "dispatch_count": 0,
        "error_message": "Não foi possível baixar o arquivo de patentes da RPI 2917 após 3 tentativas.",
        "processed_at": "2026-12-01T12:00:05",
    }
    assert body[1]["status"] == "Baixada"
    assert body[1]["error_message"] is None and body[1]["processed_at"] is None
    assert body[2]["dispatch_count"] == 3
    assert all("file_path" not in e for e in body)


def test_lista_vazia(client: TestClient, nit: dict[str, str]) -> None:
    response = client.get(URL_EDICOES, headers=nit)
    assert response.status_code == 200
    assert response.json() == []


def test_lista_sem_login(client: TestClient) -> None:
    assert client.get(URL_EDICOES).status_code == 401


def test_lista_com_perfil_autor(client: TestClient, users: dict[str, User]) -> None:
    response = client.get(URL_EDICOES, headers=auth_header(client, users["autora"].email))
    assert response.status_code == 403
