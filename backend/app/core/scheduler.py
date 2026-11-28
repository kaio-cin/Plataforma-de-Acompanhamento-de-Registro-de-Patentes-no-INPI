"""Agendamento da coleta da RPI (US08) com APScheduler.

Terças e quartas às 9h, 13h e 18h (horário de Brasília, independente do fuso do servidor),
mais uma execução cerca de 30 s depois da subida, para recuperar semanas em que o servidor
ficou parado ou dormindo. Execuções repetidas são baratas: edição já processada é pulada.

Só é iniciado pelo lifespan da aplicação quando RPI_SCHEDULER_ENABLED=true. Use um único
worker do uvicorn: cada processo teria o próprio agendador.
"""

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.database import SessionLocal
from app.services.rpi_job_service import BRAZIL_TZ, SessionFactory, run_scheduled_job

WEEKLY_JOB_ID = "rpi-semanal"
STARTUP_JOB_ID = "rpi-na-subida"
STARTUP_DELAY = timedelta(seconds=30)


def weekly_trigger() -> CronTrigger:
    return CronTrigger(day_of_week="tue,wed", hour="9,13,18", minute=0, timezone=BRAZIL_TZ)


def build_scheduler(session_factory: SessionFactory = SessionLocal, *, now: datetime | None = None) -> BackgroundScheduler:
    """Monta o agendador com os dois jobs, sem iniciá-lo."""
    scheduler = BackgroundScheduler(
        timezone=BRAZIL_TZ,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
    )
    scheduler.add_job(
        run_scheduled_job,
        weekly_trigger(),
        args=[session_factory],
        id=WEEKLY_JOB_ID,
        name="Coleta semanal da RPI",
    )
    start = (now or datetime.now(BRAZIL_TZ)) + STARTUP_DELAY
    scheduler.add_job(
        run_scheduled_job,
        DateTrigger(run_date=start, timezone=BRAZIL_TZ),
        args=[session_factory],
        id=STARTUP_JOB_ID,
        name="Coleta da RPI na subida do servidor",
    )
    return scheduler
