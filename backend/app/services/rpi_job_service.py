"""Disparo do processamento da RPI (US08): botão "Processar agora" e agendamento semanal.

Regras:
- A edição esperada é calculada pela data: a RPI sai toda terça, com número sequencial. A
  referência é a RPI 2916, publicada em 24/11/2026. "Hoje" é sempre a data de Brasília.
- Se o XML salvo no disco falhar no parse, a edição é baixada de novo uma única vez.
- O agendamento processa as edições pendentes de uma janela de 4 semanas e, no fim de TODA
  execução, tenta enviar os e-mails dos alertas pendentes, numa sessão própria.
- Os e-mails nunca são enviados no meio do processamento: só depois dos commits da edição.
"""

import logging
import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RpiEdition, RpiEditionStatus
from app.services import alert_service, rpi_download_service, rpi_processing_service
from app.services.rpi_errors import RpiError, RpiNotPublishedError, RpiParseError
from app.services.rpi_processing_service import ProcessingResult

logger = logging.getLogger(__name__)

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")

# Edição de referência para o cálculo por data (publicada numa terça).
REFERENCE_NUMBER = 2916
REFERENCE_DATE = date(2026, 11, 24)
TUESDAY = 1  # date.weekday(): segunda = 0

# O agendamento olha a edição esperada e as 3 anteriores (semanas em que o servidor ficou parado).
CATCH_UP_WEEKS = 3

SessionFactory = Callable[[], Session]

# Impede duas execuções do agendamento ao mesmo tempo no mesmo processo (ex.: a execução da
# subida coincidindo com a das 9h). Entre processos diferentes, a reserva da edição protege.
_job_lock = threading.Lock()


def today_in_brazil(moment: datetime | None = None) -> date:
    """Data de hoje no horário de Brasília (o servidor pode estar em UTC)."""
    return (moment or datetime.now(BRAZIL_TZ)).astimezone(BRAZIL_TZ).date()


def expected_edition_number(today: date) -> int:
    """Número da RPI publicada na terça mais recente (a própria data, se for terça)."""
    last_tuesday = today - timedelta(days=(today.weekday() - TUESDAY) % 7)
    return REFERENCE_NUMBER + (last_tuesday - REFERENCE_DATE).days // 7


def process_with_retry(
    db: Session, number: int, *, data_dir: Path = rpi_download_service.DEFAULT_DATA_DIR
) -> ProcessingResult:
    """Processa a edição; se o XML salvo falhar no parse, baixa de novo e tenta uma única vez.

    Os erros de process_edition chegam a quem chamou (ver rpi_errors).
    """
    try:
        return rpi_processing_service.process_edition(db, number, data_dir=data_dir)
    except RpiParseError:
        logger.warning("RPI %s: arquivo salvo não pôde ser lido; baixando de novo.", number)
        return rpi_processing_service.process_edition(db, number, data_dir=data_dir, force_download=True)


def process_now(
    db: Session,
    number: int | None = None,
    *,
    today: date | None = None,
    data_dir: Path = rpi_download_service.DEFAULT_DATA_DIR,
) -> ProcessingResult:
    """Botão "Processar agora": processa a edição pedida ou, sem número, a edição esperada pela data."""
    if number is None:
        number = expected_edition_number(today or today_in_brazil())
    return process_with_retry(db, number, data_dir=data_dir)


def pending_numbers(db: Session, expected: int) -> list[int]:
    """Edições que o agendamento deve processar, em ordem crescente.

    - Banco sem nenhuma edição: só a esperada (o histórico não é baixado).
    - Caso contrário: da maior entre (esperada - 3) e a menor edição gravada até a esperada,
      sem as que já estão "Processada". Números ausentes do banco dentro da janela entram (por
      exemplo, uma edição nova que falhou antes de ser gravada).
    - A esperada sempre entra se não estiver "Processada".
    """
    try:
        lowest = db.scalar(select(func.min(RpiEdition.number)))
        if lowest is None:
            return [expected]
        start = max(1, min(max(expected - CATCH_UP_WEEKS, lowest), expected))
        processed = set(
            db.scalars(
                select(RpiEdition.number).where(
                    RpiEdition.number.between(start, expected),
                    RpiEdition.status == RpiEditionStatus.PROCESSADA,
                )
            )
        )
    finally:
        db.rollback()  # process_edition precisa de uma sessão sem transação pendente
    return [number for number in range(start, expected + 1) if number not in processed]


def send_emails_in_new_session(session_factory: SessionFactory) -> int:
    """Envia os e-mails dos alertas pendentes numa sessão própria, fechada no fim.

    Usada depois da resposta do botão (BackgroundTasks) e no fim do agendamento. Nunca levanta
    exceção: uma falha só vai para o log. Devolve quantos e-mails saíram.
    """
    try:
        with session_factory() as db:
            sent = alert_service.send_pending_alert_emails(db)
    except Exception:
        logger.exception("Falha ao enviar os e-mails dos alertas pendentes.")
        return 0
    if sent:
        logger.info("%s e-mail(s) de alerta enviado(s).", sent)
    return sent


def run_scheduled_job(session_factory: SessionFactory, *, today: date | None = None) -> None:
    """Execução do agendamento: processa as edições pendentes e depois envia os e-mails pendentes.

    Nunca levanta exceção. O envio dos e-mails é tentado em toda execução, mesmo sem edição
    pendente, com edição não publicada, com erro ou depois de uma falha inesperada.
    """
    if not _job_lock.acquire(blocking=False):
        logger.info("Agendamento da RPI: outra execução ainda está em andamento; esta foi ignorada.")
        return
    try:
        try:
            with session_factory() as db:
                _process_pending(db, today or today_in_brazil())
        except Exception:
            logger.exception("Agendamento da RPI: falha inesperada no processamento.")
        # Sessão nova: a do processamento pode ter ficado inutilizável depois de uma falha.
        send_emails_in_new_session(session_factory)
    finally:
        _job_lock.release()


def _process_pending(db: Session, today: date) -> None:
    expected = expected_edition_number(today)
    numbers = pending_numbers(db, expected)
    if not numbers:
        logger.info("Agendamento da RPI: nenhuma edição pendente (esperada: %s).", expected)
        return

    for number in numbers:
        try:
            result = process_with_retry(db, number)
        except RpiNotPublishedError:
            # Segue para as próximas: um número da janela pode nunca ter sido publicado.
            logger.info("Agendamento da RPI: a RPI %s ainda não foi publicada.", number)
            continue
        except RpiError as exc:
            logger.warning("Agendamento da RPI: a RPI %s não foi processada: %s", number, exc)
            continue
        except Exception:
            # Uma falha inesperada numa edição não pode impedir as seguintes (inclusive a esperada).
            # Se o rollback também falhar, a exceção sobe para run_scheduled_job.
            logger.exception("Agendamento da RPI: falha inesperada na RPI %s.", number)
            db.rollback()
            continue
        logger.info(
            "Agendamento da RPI: RPI %s processada (%s despachos novos, %s alertas).",
            number,
            result.new_dispatches,
            result.alerts_created,
        )
