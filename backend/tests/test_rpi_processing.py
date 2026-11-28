"""Processamento de uma edição da RPI (US09): cruzamento, glossário, alertas, falhas e concorrência.

Sem internet: os XML das fixtures são copiados para a pasta da edição com os nomes fixos, e o
download os reaproveita. urlopen e o envio de e-mail falham o teste se forem chamados.
"""

import logging
import re
import shutil
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import Alert, Asset, AssetType, Dispatch, DispatchCode, RpiEdition, RpiEditionStatus, User
from app.services import alert_service, email_service, rpi_download_service
from app.services import rpi_processing_service as service
from app.services.rpi_errors import (
    RpiAlreadyProcessingError,
    RpiDownloadError,
    RpiNotPublishedError,
    RpiParseError,
    RpiProcessingError,
)
from app.services.rpi_processing_service import PROCESSING_TIMEOUT, UnknownCode, process_edition

FIXTURES = Path(__file__).parent / "fixtures" / "rpi"
PUBLICACAO = date(2026, 11, 24)
AGORA = datetime(2026, 11, 25, 12, 0)  # UTC sem fuso, como no service

PATENTE_6_1 = "BR 11 2021 007863-0"  # na fixture: despachos 6.1 e 15.11 (patentes)
PROGRAMA_730 = "BR 51 2026 004978-4"  # na fixture: despacho 730 (programas)


class Relogio:
    """Relógio fixo injetado em process_edition."""

    def __init__(self, agora: datetime = AGORA) -> None:
        self.agora = agora

    def __call__(self) -> datetime:
        return self.agora


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    pasta = tmp_path / "2916"
    pasta.mkdir()
    shutil.copy(FIXTURES / "patentes_2916.xml", pasta / "patentes.xml")
    shutil.copy(FIXTURES / "programas_2916.xml", pasta / "programas.xml")
    return tmp_path


@pytest.fixture(autouse=True)
def sem_internet(monkeypatch: pytest.MonkeyPatch) -> None:
    def urlopen(*_args, **_kwargs):
        raise AssertionError("o teste tentou acessar a internet")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


@pytest.fixture(autouse=True)
def sem_email(monkeypatch: pytest.MonkeyPatch) -> None:
    def send_email(*_args) -> bool:
        raise AssertionError("o processamento não pode enviar e-mail")

    monkeypatch.setattr(email_service, "send_email", send_email)


def _ativo(db: Session, numero: str, tipo: AssetType = AssetType.PATENTE, autor: User | None = None) -> Asset:
    ativo = Asset(
        title=f"Ativo {numero}",
        asset_type=tipo,
        process_number=numero,
        deposit_date=date(2021, 1, 1),
        status="Em exame",
        authors="Equipe",
        author_user=autor,
    )
    db.add(ativo)
    db.commit()
    return ativo


def _codigo(
    db: Session,
    codigo: str,
    tipo: AssetType = AssetType.PATENTE,
    *,
    exige_acao: bool = False,
    prazo: int | None = None,
) -> DispatchCode:
    criado = DispatchCode(
        code=codigo,
        asset_type=tipo,
        official_description=f"Despacho {codigo}",
        plain_description=f"Explicação do despacho {codigo}.",
        requires_action=exige_acao,
        deadline_days=prazo,
    )
    db.add(criado)
    db.commit()
    return criado


def _edicao_existente(
    db: Session,
    status: RpiEditionStatus,
    processed_at: datetime | None = AGORA,
    publicacao: date = PUBLICACAO,
    mensagem: str | None = None,
) -> RpiEdition:
    edicao = RpiEdition(
        number=2916,
        publication_date=publicacao,
        status=status,
        processed_at=processed_at,
        error_message=mensagem,
        dispatch_count=7,
    )
    db.add(edicao)
    db.commit()
    return edicao


def _processar(db: Session, data_dir: Path, relogio: Relogio | None = None, **kwargs):
    return process_edition(db, 2916, data_dir=data_dir, now=relogio or Relogio(), **kwargs)


def _edicao(db: Session) -> RpiEdition | None:
    db.expire_all()
    return db.scalar(select(RpiEdition).where(RpiEdition.number == 2916))


def _total(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def _download_que_falha(monkeypatch: pytest.MonkeyPatch, erro: Exception, antes=None) -> None:
    def download_edition(*_args, **_kwargs):
        if antes is not None:
            antes()
        raise erro

    monkeypatch.setattr(rpi_download_service, "download_edition", download_edition)


# --- Cruzamento e gravação -------------------------------------------------------------------------------------------


def test_grava_so_os_despachos_cruzados(db_session: Session, users: dict[str, User], data_dir: Path) -> None:
    _ativo(db_session, "BR11.2021.007863-0", autor=users["autora"])  # cadastrado em outro formato
    _ativo(db_session, "br 51 2026 004978-4", AssetType.PROGRAMA_DE_COMPUTADOR)
    _ativo(db_session, "BR 10 2099 000000-0")  # não aparece na RPI

    resultado = _processar(db_session, data_dir)

    despachos = db_session.scalars(select(Dispatch).order_by(Dispatch.id)).all()
    assert [(d.process_number, d.code) for d in despachos] == [
        (PATENTE_6_1, "6.1"),
        (PATENTE_6_1, "15.11"),
        (PROGRAMA_730, "730"),
    ]  # número como veio na RPI, não como cadastrado
    assert {d.publication_date for d in despachos} == {PUBLICACAO}
    assert despachos[2].description == "Expedição do Certificado de Registro"
    assert despachos[0].complement is None
    assert despachos[1].complement == "A Classificação Anterior era: H04N 19/50"

    assert (resultado.total_in_rpi, resultado.skipped_by_parser) == (11, 0)
    assert (resultado.matched, resultado.new_dispatches, resultado.existing_dispatches) == (3, 3, 0)
    assert resultado.dispatch_count == 3
    assert resultado.publication_date == PUBLICACAO


def test_edicao_fica_processada(db_session: Session, users: dict[str, User], data_dir: Path) -> None:
    _ativo(db_session, PATENTE_6_1)

    resultado = _processar(db_session, data_dir, Relogio(AGORA))

    edicao = _edicao(db_session)
    assert edicao.id == resultado.edition_id
    assert edicao.status == RpiEditionStatus.PROCESSADA
    assert edicao.publication_date == PUBLICACAO
    assert edicao.file_path == "2916"
    assert edicao.dispatch_count == 2
    assert edicao.processed_at == AGORA
    assert edicao.error_message is None


def test_formatos_antigos_pi_e_mu_cruzam(db_session: Session, users: dict[str, User], data_dir: Path) -> None:
    _ativo(db_session, "PI0002026-5")
    _ativo(db_session, "mu 6800992 5")

    resultado = _processar(db_session, data_dir)

    assert resultado.new_dispatches == 2
    assert set(db_session.scalars(select(Dispatch.process_number))) == {"PI 0002026-5", "MU 6800992-5"}


def test_alertas_para_o_nit_e_para_o_autor(db_session: Session, users: dict[str, User], data_dir: Path) -> None:
    _ativo(db_session, PATENTE_6_1, autor=users["autora"])  # 2 despachos x (NIT + autora)
    _ativo(db_session, PROGRAMA_730, AssetType.PROGRAMA_DE_COMPUTADOR)  # 1 despacho x NIT

    resultado = _processar(db_session, data_dir)

    assert resultado.alerts_created == 5
    assert _total(db_session, Alert) == 5
    destinatarios = set(db_session.scalars(select(Alert.user_id)))
    assert destinatarios == {users["nit"].id, users["autora"].id}
    # O service não envia e-mail: todos continuam pendentes.
    assert not any(db_session.scalars(select(Alert.email_sent)))


def test_numero_fora_dos_formatos_gera_aviso(
    db_session: Session, users: dict[str, User], data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _ativo(db_session, "11 2021 007863-0")  # sem o "BR": não cruza

    with caplog.at_level(logging.WARNING, logger=service.__name__):
        resultado = _processar(db_session, data_dir)

    assert resultado.matched == 0
    assert "fora dos formatos da RPI" in caplog.text
    assert "11 2021 007863-0" in caplog.text


def test_numero_de_edicao_invalido(db_session: Session, data_dir: Path) -> None:
    with pytest.raises(ValueError):
        process_edition(db_session, 0, data_dir=data_dir)


# --- Glossário -------------------------------------------------------------------------------------------------------


def test_codigo_que_exige_acao_liga_o_glossario_e_gera_prazo(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    _ativo(db_session, PATENTE_6_1, autor=users["autora"])
    codigo = _codigo(db_session, "6.1", exige_acao=True, prazo=90)

    _processar(db_session, data_dir)

    # Consulta de novo no banco, sem usar o que está em memória.
    db_session.expire_all()
    gravado = db_session.scalar(select(Dispatch.dispatch_code_id).where(Dispatch.code == "6.1"))
    assert gravado == codigo.id
    alertas = db_session.scalars(select(Alert).join(Dispatch).where(Dispatch.code == "6.1")).all()
    assert len(alertas) == 2
    assert all(a.requires_action for a in alertas)
    assert {a.deadline for a in alertas} == {date(2027, 2, 22)}


def test_mesmo_codigo_so_no_outro_tipo_nao_liga(db_session: Session, users: dict[str, User], data_dir: Path) -> None:
    _ativo(db_session, PATENTE_6_1)
    _codigo(db_session, "6.1", AssetType.PROGRAMA_DE_COMPUTADOR, exige_acao=True, prazo=90)

    resultado = _processar(db_session, data_dir)

    db_session.expire_all()
    assert db_session.scalar(select(Dispatch.dispatch_code_id).where(Dispatch.code == "6.1")) is None
    alerta = db_session.scalar(select(Alert).join(Dispatch).where(Dispatch.code == "6.1"))
    assert (alerta.requires_action, alerta.deadline) == (False, None)
    assert UnknownCode(AssetType.PATENTE, "6.1", 1) in resultado.unknown_codes


def test_codigo_fora_do_glossario_continua_e_avisa_uma_vez_por_codigo(
    db_session: Session, users: dict[str, User], data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _ativo(db_session, PATENTE_6_1)  # 6.1 e 15.11
    _ativo(db_session, "PI 0002026-5")  # 15.11
    _ativo(db_session, "MU 6800992-5")  # 15.11

    with caplog.at_level(logging.WARNING, logger=service.__name__):
        resultado = _processar(db_session, data_dir)

    assert resultado.new_dispatches == 4
    assert all(not a.requires_action and a.deadline is None for a in db_session.scalars(select(Alert)))
    assert set(resultado.unknown_codes) == {
        UnknownCode(AssetType.PATENTE, "6.1", 1),
        UnknownCode(AssetType.PATENTE, "15.11", 3),
    }
    avisos = [r.getMessage() for r in caplog.records if "fora do glossário" in r.getMessage()]
    assert len(avisos) == 2
    assert any("15.11" in aviso and "3 despacho" in aviso for aviso in avisos)


# --- Reprocessamento -------------------------------------------------------------------------------------------------


def test_reprocessar_nao_duplica_despachos_nem_alertas(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    _ativo(db_session, PATENTE_6_1, autor=users["autora"])
    _ativo(db_session, PROGRAMA_730, AssetType.PROGRAMA_DE_COMPUTADOR)
    primeiro = _processar(db_session, data_dir)

    segundo = _processar(db_session, data_dir)

    assert (segundo.new_dispatches, segundo.existing_dispatches, segundo.matched) == (0, 3, 3)
    assert segundo.alerts_created == 0
    assert segundo.dispatch_count == primeiro.dispatch_count == 3
    assert segundo.edition_id == primeiro.edition_id
    assert _total(db_session, Dispatch) == 3
    assert _total(db_session, Alert) == 5
    assert _edicao(db_session).status == RpiEditionStatus.PROCESSADA


def test_reprocessar_mantem_alerta_lido(db_session: Session, users: dict[str, User], data_dir: Path) -> None:
    _ativo(db_session, PATENTE_6_1)
    _processar(db_session, data_dir)
    alerta = db_session.scalars(select(Alert)).first()
    alerta.is_read = True
    db_session.commit()

    _processar(db_session, data_dir)

    db_session.expire_all()
    assert db_session.get(Alert, alerta.id).is_read is True


def test_glossario_carregado_depois_preenche_o_vinculo_vazio(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    _ativo(db_session, PATENTE_6_1)
    _processar(db_session, data_dir)
    codigo = _codigo(db_session, "6.1", exige_acao=True, prazo=90)

    segundo = _processar(db_session, data_dir)

    db_session.expire_all()
    assert db_session.scalar(select(Dispatch.dispatch_code_id).where(Dispatch.code == "6.1")) == codigo.id
    # Os alertas já criados não mudam (requires_action e prazo são copiados na criação).
    alerta = db_session.scalar(select(Alert).join(Dispatch).where(Dispatch.code == "6.1"))
    assert (alerta.requires_action, alerta.deadline) == (False, None)
    assert UnknownCode(AssetType.PATENTE, "6.1", 1) not in segundo.unknown_codes


def test_reprocessar_nunca_troca_vinculo_existente(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    _ativo(db_session, PATENTE_6_1)
    outro = _codigo(db_session, "15.11")
    _codigo(db_session, "6.1")
    _processar(db_session, data_dir)
    despacho = db_session.scalar(select(Dispatch).where(Dispatch.code == "6.1"))
    despacho.dispatch_code_id = outro.id  # vínculo existente, mesmo que diferente do glossário atual
    db_session.commit()

    _processar(db_session, data_dir)

    db_session.expire_all()
    assert db_session.get(Dispatch, despacho.id).dispatch_code_id == outro.id


def test_ativo_cadastrado_depois_cruza_no_reprocessamento(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    _ativo(db_session, PATENTE_6_1)
    _processar(db_session, data_dir)
    _ativo(db_session, PROGRAMA_730, AssetType.PROGRAMA_DE_COMPUTADOR)

    segundo = _processar(db_session, data_dir)

    assert (segundo.new_dispatches, segundo.existing_dispatches, segundo.dispatch_count) == (1, 2, 3)
    assert segundo.alerts_created == 1


# --- Falhas ----------------------------------------------------------------------------------------------------------


def test_falha_no_meio_desfaz_tudo_e_grava_erro(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ativo(db_session, PATENTE_6_1, autor=users["autora"])
    _ativo(db_session, PROGRAMA_730, AssetType.PROGRAMA_DE_COMPUTADOR)
    original = alert_service.create_alerts_for
    chamadas: list[int] = []

    def create_alerts_for(db, dispatch):
        chamadas.append(1)
        if len(chamadas) == 2:
            raise RuntimeError("detalhe técnico: constraint xyz violada")
        return original(db, dispatch)

    monkeypatch.setattr(alert_service, "create_alerts_for", create_alerts_for)

    with pytest.raises(RpiProcessingError) as erro:
        _processar(db_session, data_dir)

    assert isinstance(erro.value.__cause__, RuntimeError)
    assert _total(db_session, Dispatch) == 0
    assert _total(db_session, Alert) == 0
    edicao = _edicao(db_session)
    assert edicao.status == RpiEditionStatus.ERRO
    assert edicao.error_message == "Falha ao cruzar a RPI 2916 com os processos cadastrados. Tente processar de novo."
    assert "constraint" not in edicao.error_message  # o texto técnico vai só para o log

    monkeypatch.setattr(alert_service, "create_alerts_for", original)
    resultado = _processar(db_session, data_dir)

    assert resultado.new_dispatches == 3
    assert _edicao(db_session).status == RpiEditionStatus.PROCESSADA


def test_falha_ao_gravar_o_erro_nao_esconde_a_original(
    db_session: Session,
    users: dict[str, User],
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _ativo(db_session, PATENTE_6_1)
    estado = {"banco_fora": False}
    commit_original = db_session.commit

    def create_alerts_for(db, dispatch):
        estado["banco_fora"] = True
        raise RuntimeError("falha simulada")

    def commit() -> None:
        if estado["banco_fora"]:
            raise OperationalError("UPDATE rpi_editions", {}, Exception("banco indisponível"))
        commit_original()

    monkeypatch.setattr(alert_service, "create_alerts_for", create_alerts_for)
    monkeypatch.setattr(db_session, "commit", commit)

    with caplog.at_level(logging.WARNING, logger=service.__name__):
        with pytest.raises(RpiProcessingError):
            _processar(db_session, data_dir)

    assert "Não foi possível registrar o erro" in caplog.text


def test_parse_falha_em_edicao_nova_nao_grava_nada(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    (data_dir / "2916" / "patentes.xml").write_text("isto não é xml", encoding="utf-8")

    with pytest.raises(RpiParseError):
        _processar(db_session, data_dir)

    assert _edicao(db_session) is None


@pytest.mark.parametrize("status", [RpiEditionStatus.ERRO, RpiEditionStatus.BAIXADA])
def test_parse_falha_em_edicao_com_erro_ou_baixada_grava_erro(
    status: RpiEditionStatus, db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    _edicao_existente(db_session, status, processed_at=AGORA - timedelta(days=1), mensagem="erro antigo")
    (data_dir / "2916" / "patentes.xml").write_text("isto não é xml", encoding="utf-8")

    with pytest.raises(RpiParseError) as erro:
        _processar(db_session, data_dir, Relogio(AGORA))

    edicao = _edicao(db_session)
    assert edicao.status == RpiEditionStatus.ERRO
    assert edicao.error_message == str(erro.value)
    assert edicao.processed_at == AGORA


def test_falha_de_download_em_edicao_processada_nao_muda_nada(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    antes = AGORA - timedelta(days=1)
    _edicao_existente(db_session, RpiEditionStatus.PROCESSADA, processed_at=antes)
    _download_que_falha(monkeypatch, RpiDownloadError("Não foi possível baixar o arquivo de patentes da RPI 2916."))

    with pytest.raises(RpiDownloadError):
        _processar(db_session, data_dir, force_download=True)

    edicao = _edicao(db_session)
    assert (edicao.status, edicao.processed_at, edicao.error_message, edicao.dispatch_count) == (
        RpiEditionStatus.PROCESSADA,
        antes,
        None,
        7,
    )


def test_falha_de_download_em_edicao_com_erro_atualiza_a_mensagem(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _edicao_existente(db_session, RpiEditionStatus.ERRO, processed_at=AGORA - timedelta(days=1), mensagem="antiga")
    mensagem = "Não foi possível baixar o arquivo de patentes da RPI 2916 após 3 tentativas."
    _download_que_falha(monkeypatch, RpiDownloadError(mensagem))

    with pytest.raises(RpiDownloadError):
        _processar(db_session, data_dir)

    edicao = _edicao(db_session)
    assert (edicao.status, edicao.error_message, edicao.processed_at) == (RpiEditionStatus.ERRO, mensagem, AGORA)


def test_outra_chamada_reserva_durante_o_download_que_falha(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _edicao_existente(db_session, RpiEditionStatus.ERRO, processed_at=AGORA - timedelta(days=1))

    def outra_chamada_reserva() -> None:
        with Session(bind=db_session.get_bind()) as outra:
            edicao = outra.scalar(select(RpiEdition).where(RpiEdition.number == 2916))
            edicao.status = RpiEditionStatus.PROCESSANDO
            edicao.processed_at = AGORA
            outra.commit()

    _download_que_falha(monkeypatch, RpiDownloadError("Falha simulada no download."), antes=outra_chamada_reserva)

    with pytest.raises(RpiDownloadError):
        _processar(db_session, data_dir, Relogio(AGORA))

    edicao = _edicao(db_session)
    assert edicao.status == RpiEditionStatus.PROCESSANDO
    assert edicao.processed_at == AGORA


def test_edicao_nao_publicada_nunca_grava_nada(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _edicao_existente(db_session, RpiEditionStatus.ERRO, processed_at=AGORA - timedelta(days=1), mensagem="antiga")
    _download_que_falha(monkeypatch, RpiNotPublishedError("A RPI 2916 ainda não foi publicada pelo INPI."))

    with pytest.raises(RpiNotPublishedError):
        _processar(db_session, data_dir)

    edicao = _edicao(db_session)
    assert (edicao.status, edicao.error_message) == (RpiEditionStatus.ERRO, "antiga")


def test_edicao_nova_nao_publicada_nao_e_criada(
    db_session: Session, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _download_que_falha(monkeypatch, RpiNotPublishedError("A RPI 2916 ainda não foi publicada pelo INPI."))

    with pytest.raises(RpiNotPublishedError):
        _processar(db_session, data_dir)

    assert _edicao(db_session) is None


def test_force_download_e_repassado(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = rpi_download_service.download_edition
    chamadas: list[dict] = []

    def download_edition(number, data_dir, **kwargs):
        chamadas.append(kwargs)
        return original(number, data_dir)  # sem force, para reaproveitar as fixtures sem internet

    monkeypatch.setattr(rpi_download_service, "download_edition", download_edition)

    _processar(db_session, data_dir, force_download=True)

    assert chamadas == [{"force": True}]


def test_data_diferente_da_registrada_vira_erro(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    _edicao_existente(db_session, RpiEditionStatus.PROCESSADA, publicacao=date(2026, 11, 17))
    _ativo(db_session, PATENTE_6_1)

    with pytest.raises(RpiProcessingError, match="data de publicação"):
        _processar(db_session, data_dir)

    edicao = _edicao(db_session)
    assert edicao.status == RpiEditionStatus.ERRO
    assert "24/11/2026" in edicao.error_message
    assert _total(db_session, Dispatch) == 0


# --- Concorrência e edição travada -----------------------------------------------------------------------------------


def test_edicao_em_processamento_recente_nao_e_baixada(
    db_session: Session, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _edicao_existente(db_session, RpiEditionStatus.PROCESSANDO, processed_at=AGORA - timedelta(minutes=9))
    _download_que_falha(monkeypatch, AssertionError("não deveria baixar"))

    with pytest.raises(RpiAlreadyProcessingError, match="já está sendo processada"):
        _processar(db_session, data_dir, Relogio(AGORA))


def test_edicao_presa_alem_do_limite_e_retomada(db_session: Session, users: dict[str, User], data_dir: Path) -> None:
    _edicao_existente(db_session, RpiEditionStatus.PROCESSANDO, processed_at=AGORA - PROCESSING_TIMEOUT - timedelta(seconds=1))
    _ativo(db_session, PATENTE_6_1)

    resultado = _processar(db_session, data_dir, Relogio(AGORA))

    assert resultado.new_dispatches == 2
    assert _edicao(db_session).status == RpiEditionStatus.PROCESSADA


def test_outra_chamada_insere_a_edicao_antes_da_reserva(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simula a corrida: a edição não existia na consulta da reserva, mas outra chamada a inseriu antes do INSERT."""
    _ativo(db_session, PATENTE_6_1)
    original = rpi_download_service.download_edition

    def download_edition(number, data_dir, **kwargs):
        with Session(bind=db_session.get_bind()) as outra:
            outra.add(
                RpiEdition(
                    number=2916,
                    publication_date=PUBLICACAO,
                    status=RpiEditionStatus.PROCESSANDO,
                    processed_at=AGORA,
                )
            )
            outra.commit()
        return original(number, data_dir)

    scalar_original = db_session.scalar
    primeira_consulta = {"feita": False}

    def scalar(statement, *args, **kwargs):
        # A primeira consulta do id da edição "não vê" a edição recém-inserida pela outra chamada.
        if not primeira_consulta["feita"] and "rpi_editions.id" in str(statement):
            primeira_consulta["feita"] = True
            return None
        return scalar_original(statement, *args, **kwargs)

    monkeypatch.setattr(rpi_download_service, "download_edition", download_edition)
    monkeypatch.setattr(db_session, "scalar", scalar)

    with pytest.raises(RpiAlreadyProcessingError):
        _processar(db_session, data_dir, Relogio(AGORA))

    assert primeira_consulta["feita"]
    assert _total(db_session, Dispatch) == 0
    assert _edicao(db_session).status == RpiEditionStatus.PROCESSANDO


# --- Casos especiais -------------------------------------------------------------------------------------------------


def test_ativos_ambiguos_do_mesmo_tipo_ficam_com_o_menor_id(
    db_session: Session, users: dict[str, User], data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    primeiro = _ativo(db_session, PATENTE_6_1)
    _ativo(db_session, "BR11 2021 007863-0")  # mesmo processo, outro texto

    with caplog.at_level(logging.WARNING, logger=service.__name__):
        resultado = _processar(db_session, data_dir)

    assert set(db_session.scalars(select(Dispatch.asset_id))) == {primeiro.id}
    assert resultado.ambiguous_processes == (PATENTE_6_1,)  # dois despachos, listado uma vez
    assert resultado.type_mismatches == ()
    assert "corresponde a 2 ativos" in caplog.text


def test_ativos_ambiguos_com_tipos_diferentes_vence_o_do_tipo_certo(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    _ativo(db_session, PATENTE_6_1, AssetType.PROGRAMA_DE_COMPUTADOR)  # menor id, tipo errado
    certo = _ativo(db_session, "BR 11.2021.007863-0", AssetType.PATENTE)

    resultado = _processar(db_session, data_dir)

    assert set(db_session.scalars(select(Dispatch.asset_id))) == {certo.id}
    assert resultado.ambiguous_processes == (PATENTE_6_1,)
    assert resultado.type_mismatches == ()


def test_tipo_diferente_da_secao_grava_e_avisa(
    db_session: Session, users: dict[str, User], data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _ativo(db_session, PATENTE_6_1, AssetType.PROGRAMA_DE_COMPUTADOR)
    codigo = _codigo(db_session, "6.1", AssetType.PATENTE)  # o glossário usa o tipo do XML

    with caplog.at_level(logging.WARNING, logger=service.__name__):
        resultado = _processar(db_session, data_dir)

    assert resultado.new_dispatches == 2
    assert resultado.type_mismatches == (PATENTE_6_1,)
    assert db_session.scalar(select(Dispatch.dispatch_code_id).where(Dispatch.code == "6.1")) == codigo.id
    assert "seção de Patente" in caplog.text


def test_despacho_gravado_nao_troca_de_ativo(db_session: Session, users: dict[str, User], data_dir: Path) -> None:
    errado = _ativo(db_session, PATENTE_6_1, AssetType.PROGRAMA_DE_COMPUTADOR)
    _processar(db_session, data_dir)
    _ativo(db_session, "BR11 2021 007863-0", AssetType.PATENTE)  # agora há um do tipo certo

    segundo = _processar(db_session, data_dir)

    assert set(db_session.scalars(select(Dispatch.asset_id))) == {errado.id}
    assert segundo.existing_dispatches == 2
    assert segundo.ambiguous_processes == (PATENTE_6_1,)
    assert segundo.type_mismatches == (PATENTE_6_1,)  # o ativo do despacho gravado tem tipo diferente


def test_par_repetido_no_xml_conta_so_em_duplicates(
    db_session: Session, users: dict[str, User], data_dir: Path
) -> None:
    arquivo = data_dir / "2916" / "patentes.xml"
    texto = arquivo.read_text(encoding="utf-8")
    bloco = re.search(r"  <despacho>\s*<codigo>6\.1</codigo>.*?</despacho>\n", texto, re.DOTALL).group(0)
    arquivo.write_text(texto.replace(bloco, bloco + bloco), encoding="utf-8")
    _ativo(db_session, PATENTE_6_1)

    resultado = _processar(db_session, data_dir)

    assert resultado.total_in_rpi == 12
    assert resultado.duplicates_in_rpi == 1
    assert (resultado.matched, resultado.new_dispatches) == (2, 2)
    assert resultado.matched == resultado.new_dispatches + resultado.existing_dispatches
    assert UnknownCode(AssetType.PATENTE, "6.1", 1) in resultado.unknown_codes  # a repetição não conta


# --- Falha de banco antes da reserva ---------------------------------------------------------------------------------

MENSAGEM_INICIO = "Não foi possível iniciar o processamento da RPI 2916. Tente de novo em alguns minutos."


def _banco_travado_uma_vez(monkeypatch: pytest.MonkeyPatch, db: Session, metodo: str, trecho_sql: str) -> list[str]:
    """Faz db.<metodo> levantar OperationalError ("database is locked") na primeira consulta que contém trecho_sql."""
    original = getattr(db, metodo)
    falhas: list[str] = []

    def travado(statement, *args, **kwargs):
        if not falhas and trecho_sql in str(statement):
            falhas.append(str(statement))
            raise OperationalError(str(statement), {}, Exception("database is locked"))
        return original(statement, *args, **kwargs)

    monkeypatch.setattr(db, metodo, travado)
    return falhas


def _confere_falha_de_inicio(db: Session, erro: pytest.ExceptionInfo, falhas: list[str]) -> None:
    assert falhas, "a falha simulada não foi acionada"
    assert str(erro.value) == MENSAGEM_INICIO
    assert "locked" not in str(erro.value) and "SELECT" not in str(erro.value)
    assert isinstance(erro.value.__cause__, OperationalError)
    assert _total(db, Dispatch) == 0
    assert _total(db, Alert) == 0


def test_banco_falha_na_checagem_inicial(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ativo(db_session, PATENTE_6_1)
    falhas = _banco_travado_uma_vez(monkeypatch, db_session, "execute", "rpi_editions.status")

    with pytest.raises(RpiProcessingError) as erro:
        _processar(db_session, data_dir)

    _confere_falha_de_inicio(db_session, erro, falhas)
    assert _edicao(db_session) is None
    # A sessão continua utilizável: o processamento seguinte funciona.
    assert _processar(db_session, data_dir).new_dispatches == 2


def test_banco_falha_na_checagem_inicial_de_edicao_existente(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    antes = AGORA - timedelta(days=1)
    _edicao_existente(db_session, RpiEditionStatus.ERRO, processed_at=antes, mensagem="antiga")
    falhas = _banco_travado_uma_vez(monkeypatch, db_session, "execute", "rpi_editions.status")

    with pytest.raises(RpiProcessingError) as erro:
        _processar(db_session, data_dir)

    _confere_falha_de_inicio(db_session, erro, falhas)
    edicao = _edicao(db_session)
    assert (edicao.status, edicao.error_message, edicao.processed_at) == (RpiEditionStatus.ERRO, "antiga", antes)


def test_banco_falha_na_reserva_de_edicao_nova(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ativo(db_session, PATENTE_6_1)
    falhas = _banco_travado_uma_vez(monkeypatch, db_session, "scalar", "rpi_editions.id")

    with pytest.raises(RpiProcessingError) as erro:
        _processar(db_session, data_dir)

    _confere_falha_de_inicio(db_session, erro, falhas)
    assert _edicao(db_session) is None
    assert _processar(db_session, data_dir).new_dispatches == 2


def test_banco_falha_na_reserva_de_edicao_existente(
    db_session: Session, users: dict[str, User], data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    antes = AGORA - timedelta(days=1)
    _edicao_existente(db_session, RpiEditionStatus.PROCESSADA, processed_at=antes)
    _ativo(db_session, PATENTE_6_1)
    falhas = _banco_travado_uma_vez(monkeypatch, db_session, "execute", "UPDATE rpi_editions")

    with pytest.raises(RpiProcessingError) as erro:
        _processar(db_session, data_dir)

    _confere_falha_de_inicio(db_session, erro, falhas)
    edicao = _edicao(db_session)
    assert (edicao.status, edicao.processed_at, edicao.error_message, edicao.dispatch_count) == (
        RpiEditionStatus.PROCESSADA,
        antes,
        None,
        7,
    )
    assert _processar(db_session, data_dir).new_dispatches == 2
