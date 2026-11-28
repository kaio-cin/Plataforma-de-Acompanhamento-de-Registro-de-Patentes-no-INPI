"""Disparo do processamento da RPI (US08): edição esperada, nova tentativa, pendentes e agendamento.

Sem internet, sem e-mail de verdade e sem o banco real: process_edition e send_email são
trocados por falsos, e as sessões do agendamento abrem o banco em memória do teste.
"""

import urllib.request
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Alert, Asset, Dispatch, RpiEdition, RpiEditionStatus, User
from app.services import email_service, rpi_job_service, rpi_processing_service
from app.services.alert_service import create_alerts_for
from app.services.rpi_errors import (
    RpiAlreadyProcessingError,
    RpiDownloadError,
    RpiNotPublishedError,
    RpiParseError,
)
from app.services.rpi_job_service import expected_edition_number, pending_numbers, today_in_brazil

TERCA_2917 = date(2026, 12, 1)  # publicação da RPI 2917: a edição esperada é 2917


@pytest.fixture(autouse=True)
def sem_internet(monkeypatch: pytest.MonkeyPatch) -> None:
    def urlopen(*_args, **_kwargs):
        raise AssertionError("o teste tentou acessar a internet")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


@pytest.fixture
def enviados(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Troca send_email por um falso que registra o destinatário e sempre dá certo."""
    destinatarios: list[str] = []

    def send_email(to: str, _subject: str, _body: str) -> bool:
        destinatarios.append(to)
        return True

    monkeypatch.setattr(email_service, "send_email", send_email)
    return destinatarios


@pytest.fixture
def fabrica(db_session: Session) -> sessionmaker:
    """Fábrica de sessões do banco em memória (a que o agendamento recebe)."""
    return sessionmaker(bind=db_session.get_bind(), autoflush=False, expire_on_commit=False)


class ProcessamentoFalso:
    """Substitui process_edition: registra as chamadas e levanta o erro configurado por número."""

    def __init__(self, erros: dict[int, Exception] | None = None) -> None:
        self.erros = erros or {}
        self.chamadas: list[tuple[int, bool]] = []

    def __call__(self, _db: Session, number: int, *, data_dir=None, force_download: bool = False, **_kwargs):
        self.chamadas.append((number, force_download))
        erro = self.erros.get(number)
        if erro is not None:
            raise erro
        return rpi_processing_service.ProcessingResult(
            edition_id=1,
            number=number,
            publication_date=date(2026, 11, 24),
            total_in_rpi=0,
            skipped_by_parser=0,
            matched=0,
            new_dispatches=0,
            existing_dispatches=0,
            dispatch_count=0,
            alerts_created=0,
            unknown_codes=(),
            type_mismatches=(),
            ambiguous_processes=(),
            duplicates_in_rpi=0,
        )

    @property
    def numeros(self) -> list[int]:
        return [numero for numero, _ in self.chamadas]


def _usar(monkeypatch: pytest.MonkeyPatch, falso: ProcessamentoFalso) -> ProcessamentoFalso:
    monkeypatch.setattr(rpi_processing_service, "process_edition", falso)
    return falso


def _edicoes(db: Session, **por_numero: RpiEditionStatus) -> None:
    """Grava edições: _edicoes(db, n2916=ERRO, n2917=PROCESSADA)."""
    for chave, situacao in por_numero.items():
        db.add(RpiEdition(number=int(chave[1:]), publication_date=date(2026, 11, 24), status=situacao))
    db.commit()


# --- Edição esperada pela data ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hoje", "esperada"),
    [
        (date(2026, 11, 23), 2915),  # segunda antes da referência
        (date(2026, 11, 24), 2916),  # terça da referência
        (date(2026, 11, 30), 2916),  # segunda seguinte
        (date(2026, 12, 1), 2917),  # terça
        (date(2026, 12, 7), 2917),  # segunda da apresentação
        (date(2027, 1, 5), 2922),  # virada do ano
    ],
)
def test_edicao_esperada_pela_data(hoje: date, esperada: int) -> None:
    assert expected_edition_number(hoje) == esperada


def test_semana_de_feriado_terca_e_quarta_dao_o_mesmo_numero() -> None:
    # Se a RPI atrasar para quarta (feriado na terça), as execuções de terça e quarta buscam a mesma edição.
    assert expected_edition_number(date(2026, 12, 1)) == expected_edition_number(date(2026, 12, 2)) == 2917


def test_hoje_e_calculado_no_horario_de_brasilia() -> None:
    # Terça 01/12 às 02h30 em UTC ainda é segunda 30/11 às 23h30 em Brasília.
    momento = datetime(2026, 12, 1, 2, 30, tzinfo=UTC)
    assert today_in_brazil(momento) == date(2026, 11, 30)
    assert expected_edition_number(today_in_brazil(momento)) == 2916


# --- Nova tentativa em erro de leitura -------------------------------------------------------------------------------


def test_erro_de_leitura_baixa_de_novo_uma_vez(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    class FalhaSoNaPrimeira(ProcessamentoFalso):
        def __call__(self, db, number, *, force_download=False, **kwargs):
            if not force_download:
                self.chamadas.append((number, force_download))
                raise RpiParseError("O XML da RPI 2916 não pôde ser lido.")
            return super().__call__(db, number, force_download=force_download, **kwargs)

    falso = _usar(monkeypatch, FalhaSoNaPrimeira())

    resultado = rpi_job_service.process_with_retry(db_session, 2916)

    assert resultado.number == 2916
    assert falso.chamadas == [(2916, False), (2916, True)]


def test_erro_de_leitura_repetido_chega_a_quem_chamou(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    falso = _usar(monkeypatch, ProcessamentoFalso({2916: RpiParseError("O XML da RPI 2916 não pôde ser lido.")}))

    with pytest.raises(RpiParseError):
        rpi_job_service.process_with_retry(db_session, 2916)
    assert falso.chamadas == [(2916, False), (2916, True)]


@pytest.mark.parametrize(
    "erro",
    [
        RpiDownloadError("falha"),
        RpiNotPublishedError("não publicada"),
        RpiAlreadyProcessingError("ocupada"),
    ],
)
def test_outros_erros_nao_baixam_de_novo(db_session: Session, monkeypatch: pytest.MonkeyPatch, erro) -> None:
    falso = _usar(monkeypatch, ProcessamentoFalso({2916: erro}))

    with pytest.raises(type(erro)):
        rpi_job_service.process_with_retry(db_session, 2916)
    assert falso.chamadas == [(2916, False)]


def test_processar_agora_sem_numero_usa_a_edicao_esperada(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    falso = _usar(monkeypatch, ProcessamentoFalso())

    rpi_job_service.process_now(db_session, today=date(2026, 12, 7))
    rpi_job_service.process_now(db_session, 2900, today=date(2026, 12, 7))

    assert falso.numeros == [2917, 2900]


# --- Edições pendentes -----------------------------------------------------------------------------------------------


def test_banco_vazio_so_a_esperada(db_session: Session) -> None:
    assert pending_numbers(db_session, 2917) == [2917]


def test_edicao_com_erro_antes_da_esperada_processada_fica_pendente(db_session: Session) -> None:
    _edicoes(db_session, n2916=RpiEditionStatus.ERRO, n2917=RpiEditionStatus.PROCESSADA)
    assert pending_numbers(db_session, 2917) == [2916]


def test_so_uma_edicao_muito_antiga_limita_a_janela(db_session: Session) -> None:
    _edicoes(db_session, n2800=RpiEditionStatus.ERRO)
    assert pending_numbers(db_session, 2917) == [2914, 2915, 2916, 2917]


def test_edicao_ausente_no_meio_da_janela_entra(db_session: Session) -> None:
    # A 2915 nunca foi gravada (por exemplo, falhou no download antes da reserva).
    _edicoes(db_session, n2914=RpiEditionStatus.PROCESSADA, n2916=RpiEditionStatus.PROCESSADA)
    assert pending_numbers(db_session, 2917) == [2915, 2917]


def test_janela_comeca_na_menor_edicao_gravada(db_session: Session) -> None:
    _edicoes(db_session, n2916=RpiEditionStatus.PROCESSADA)
    assert pending_numbers(db_session, 2917) == [2917]


def test_esperada_entra_mesmo_com_edicao_gravada_maior(db_session: Session) -> None:
    _edicoes(db_session, n2920=RpiEditionStatus.ERRO)
    assert pending_numbers(db_session, 2917) == [2917]


def test_tudo_processado_nao_tem_pendente(db_session: Session) -> None:
    _edicoes(
        db_session,
        n2914=RpiEditionStatus.PROCESSADA,
        n2915=RpiEditionStatus.PROCESSADA,
        n2916=RpiEditionStatus.PROCESSADA,
        n2917=RpiEditionStatus.PROCESSADA,
    )
    assert pending_numbers(db_session, 2917) == []


def test_edicao_em_processamento_continua_pendente(db_session: Session) -> None:
    # A reserva do service decide se ela está ocupada; aqui só "Processada" sai da lista.
    _edicoes(db_session, n2916=RpiEditionStatus.PROCESSADA, n2917=RpiEditionStatus.PROCESSANDO)
    assert pending_numbers(db_session, 2917) == [2917]


# --- Execução do agendamento -----------------------------------------------------------------------------------------


@pytest.fixture
def alerta_pendente(db_session: Session, users: dict[str, User], assets: list[Asset]) -> list[Alert]:
    """Edição 2917 já processada, com alertas cujo e-mail ainda não saiu (email_sent=False)."""
    edicao = RpiEdition(number=2917, publication_date=TERCA_2917, status=RpiEditionStatus.PROCESSADA)
    despacho = Dispatch(
        edition=edicao,
        asset=assets[0],
        process_number=assets[0].process_number,
        code="6.1",
        description="Exigência técnica",
        publication_date=TERCA_2917,
    )
    db_session.add_all([edicao, despacho])
    criados = create_alerts_for(db_session, despacho)
    db_session.commit()
    return criados


def test_execucao_processa_os_pendentes_em_ordem(
    db_session: Session, fabrica: sessionmaker, monkeypatch: pytest.MonkeyPatch, enviados: list[str]
) -> None:
    _edicoes(db_session, n2915=RpiEditionStatus.ERRO)
    falso = _usar(monkeypatch, ProcessamentoFalso())

    rpi_job_service.run_scheduled_job(fabrica, today=TERCA_2917)

    assert falso.numeros == [2915, 2916, 2917]


def test_nao_publicada_e_erro_nao_interrompem_as_seguintes(
    db_session: Session, fabrica: sessionmaker, monkeypatch: pytest.MonkeyPatch, enviados: list[str]
) -> None:
    _edicoes(db_session, n2914=RpiEditionStatus.ERRO)
    falso = _usar(
        monkeypatch,
        ProcessamentoFalso({2914: RpiNotPublishedError("não publicada"), 2915: RpiDownloadError("falha")}),
    )

    rpi_job_service.run_scheduled_job(fabrica, today=TERCA_2917)

    assert falso.numeros == [2914, 2915, 2916, 2917]


def test_falha_inesperada_numa_edicao_nao_interrompe_as_seguintes(
    db_session: Session,
    fabrica: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
    enviados: list[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _edicoes(db_session, n2914=RpiEditionStatus.ERRO)
    falso = _usar(monkeypatch, ProcessamentoFalso({2914: RuntimeError("defeito inesperado")}))

    rpi_job_service.run_scheduled_job(fabrica, today=TERCA_2917)  # não pode levantar exceção

    assert falso.numeros == [2914, 2915, 2916, 2917]
    assert "falha inesperada na RPI 2914" in caplog.text


def test_execucao_sem_pendentes_reenvia_alerta_pendente(
    db_session: Session,
    fabrica: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
    enviados: list[str],
    alerta_pendente: list[Alert],
) -> None:
    falso = _usar(monkeypatch, ProcessamentoFalso())

    rpi_job_service.run_scheduled_job(fabrica, today=TERCA_2917)

    assert falso.chamadas == []  # 2917 já processada e nenhuma edição anterior gravada
    assert sorted(enviados) == ["autora@teste.edu.br", "nit@teste.edu.br"]
    db_session.expire_all()
    assert all(db_session.scalars(select(Alert.email_sent)))


def test_edicao_nao_publicada_ainda_envia_os_pendentes(
    db_session: Session,
    fabrica: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
    enviados: list[str],
    alerta_pendente: list[Alert],
) -> None:
    _usar(monkeypatch, ProcessamentoFalso({2918: RpiNotPublishedError("não publicada")}))

    rpi_job_service.run_scheduled_job(fabrica, today=date(2026, 12, 8))  # esperada: 2918

    assert len(enviados) == 2


def test_falha_inesperada_nao_se_propaga_e_ainda_envia(
    db_session: Session,
    fabrica: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
    enviados: list[str],
    alerta_pendente: list[Alert],
) -> None:
    _usar(monkeypatch, ProcessamentoFalso({2918: RuntimeError("defeito inesperado")}))

    rpi_job_service.run_scheduled_job(fabrica, today=date(2026, 12, 8))

    assert len(enviados) == 2


def test_falha_no_envio_so_vai_para_o_log(
    db_session: Session, fabrica: sessionmaker, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _usar(monkeypatch, ProcessamentoFalso())

    def quebra(_db):
        raise RuntimeError("SMTP fora do ar")

    monkeypatch.setattr(rpi_job_service.alert_service, "send_pending_alert_emails", quebra)

    rpi_job_service.run_scheduled_job(fabrica, today=TERCA_2917)

    assert "Falha ao enviar os e-mails" in caplog.text


def test_sessoes_do_agendamento_sao_fechadas(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, enviados: list[str]
) -> None:
    fechadas: list[Session] = []

    class SessaoRegistrada(Session):
        def close(self) -> None:
            fechadas.append(self)
            super().close()

    fabrica = sessionmaker(bind=db_session.get_bind(), class_=SessaoRegistrada, expire_on_commit=False)
    _usar(monkeypatch, ProcessamentoFalso({2917: RuntimeError("defeito inesperado")}))

    rpi_job_service.run_scheduled_job(fabrica, today=TERCA_2917)

    assert len(fechadas) == 2  # uma do processamento e outra dos e-mails


def test_execucao_simultanea_e_ignorada(
    fabrica: sessionmaker, monkeypatch: pytest.MonkeyPatch, enviados: list[str]
) -> None:
    falso = _usar(monkeypatch, ProcessamentoFalso())

    with rpi_job_service._job_lock:
        rpi_job_service.run_scheduled_job(fabrica, today=TERCA_2917)

    assert falso.chamadas == []


def test_envio_em_sessao_nova_nao_levanta_excecao() -> None:
    def fabrica_quebrada():
        raise RuntimeError("banco fora do ar")

    assert rpi_job_service.send_emails_in_new_session(fabrica_quebrada) == 0
