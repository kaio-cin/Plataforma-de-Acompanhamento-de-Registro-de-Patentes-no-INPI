"""Agendamento da coleta da RPI (US08): horários, fuso e ligação com o lifespan.

O agendador nunca é iniciado de verdade: os horários são conferidos direto no trigger, e o
lifespan é testado com um agendador falso e sem criar o banco real.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core import scheduler as agendamento
from app.core.config import Settings, settings
from app.services.rpi_job_service import run_scheduled_job

BRASILIA = ZoneInfo("America/Sao_Paulo")


def _proximas(quantidade: int, a_partir_de: datetime) -> list[datetime]:
    trigger = agendamento.weekly_trigger()
    execucoes: list[datetime] = []
    anterior = None
    agora = a_partir_de
    for _ in range(quantidade):
        proxima = trigger.get_next_fire_time(anterior, agora)
        execucoes.append(proxima)
        anterior = agora = proxima
    return execucoes


def test_proximas_execucoes_tercas_e_quartas_no_horario_de_brasilia() -> None:
    # Domingo 29/11/2026, meio-dia em Brasília.
    execucoes = _proximas(7, datetime(2026, 11, 29, 12, 0, tzinfo=BRASILIA))

    assert [(e.day, e.hour) for e in execucoes] == [(1, 9), (1, 13), (1, 18), (2, 9), (2, 13), (2, 18), (8, 9)]
    assert all(e.weekday() in (1, 2) and e.minute == 0 for e in execucoes)
    assert all(e.utcoffset() == BRASILIA.utcoffset(e.replace(tzinfo=None)) for e in execucoes)
    # Brasília sem horário de verão: 9h locais = 12h UTC.
    assert execucoes[0].astimezone(ZoneInfo("UTC")).hour == 12


def test_fuso_do_trigger_independe_do_servidor() -> None:
    # A partir de um instante em UTC, a próxima execução continua às 9h de Brasília.
    proxima = _proximas(1, datetime(2026, 12, 1, 3, 0, tzinfo=ZoneInfo("UTC")))[0]
    assert (proxima.astimezone(BRASILIA).day, proxima.astimezone(BRASILIA).hour) == (1, 9)


def test_agendador_montado_sem_iniciar() -> None:
    agora = datetime(2026, 12, 1, 8, 0, tzinfo=BRASILIA)
    montado = agendamento.build_scheduler(now=agora)
    try:
        assert not montado.running
        jobs = {job.id: job for job in montado.get_jobs()}
        assert set(jobs) == {agendamento.WEEKLY_JOB_ID, agendamento.STARTUP_JOB_ID}
        assert all(job.func is run_scheduled_job for job in jobs.values())
        assert str(montado.timezone) == "America/Sao_Paulo"
        assert montado._job_defaults["max_instances"] == 1
        assert montado._job_defaults["coalesce"] is True

        subida = jobs[agendamento.STARTUP_JOB_ID].trigger.get_next_fire_time(None, agora)
        assert subida == datetime(2026, 12, 1, 8, 0, 30, tzinfo=BRASILIA)
    finally:
        assert not montado.running


def test_agendador_desligado_por_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RPI_SCHEDULER_ENABLED", raising=False)
    assert Settings(_env_file=None).rpi_scheduler_enabled is False


class AgendadorFalso:
    def __init__(self) -> None:
        self.eventos: list[str] = []

    def start(self) -> None:
        self.eventos.append("start")

    def shutdown(self, wait: bool = True) -> None:
        self.eventos.append(f"shutdown(wait={wait})")


@pytest.fixture
def lifespan_sem_banco(monkeypatch: pytest.MonkeyPatch) -> AgendadorFalso:
    """Lifespan sem criar o banco real e com um agendador falso."""
    falso = AgendadorFalso()
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "build_scheduler", lambda: falso)
    return falso


def test_lifespan_com_agendador_desligado_nao_inicia(
    monkeypatch: pytest.MonkeyPatch, lifespan_sem_banco: AgendadorFalso
) -> None:
    monkeypatch.setattr(settings, "rpi_scheduler_enabled", False)

    with TestClient(main.create_app()):
        pass

    assert lifespan_sem_banco.eventos == []


def test_lifespan_com_agendador_ligado_inicia_e_para(
    monkeypatch: pytest.MonkeyPatch, lifespan_sem_banco: AgendadorFalso
) -> None:
    monkeypatch.setattr(settings, "rpi_scheduler_enabled", True)

    with TestClient(main.create_app()):
        assert lifespan_sem_banco.eventos == ["start"]

    assert lifespan_sem_banco.eventos == ["start", "shutdown(wait=False)"]
