from collections.abc import Sequence
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, status

from app.models import RpiEdition
from app.routes.deps import DbSession, NitUser, SessionFactory
from app.schemas.rpi import RpiEditionRead, RpiProcessRequest, RpiProcessResponse
from app.services import rpi_edition_service, rpi_job_service
from app.services.rpi_errors import (
    RpiAlreadyProcessingError,
    RpiDownloadError,
    RpiError,
    RpiNotPublishedError,
    RpiParseError,
)

router = APIRouter(prefix="/rpi", tags=["RPI"])


@router.post(
    "/process",
    response_model=RpiProcessResponse,
    summary='Processa uma edição da RPI agora ("Processar agora", US08) — apenas perfil NIT',
    responses={
        403: {"description": "Usuário sem perfil NIT"},
        404: {"description": "Edição ainda não publicada pelo INPI"},
        409: {"description": "A edição já está sendo processada"},
        422: {"description": "Número de edição inválido"},
        500: {"description": "Falha ao cruzar ou gravar a edição"},
        502: {"description": "Falha no download ou arquivo do INPI ilegível"},
    },
)
def process_rpi(
    background: BackgroundTasks,
    db: DbSession,
    session_factory: SessionFactory,
    _user: NitUser,
    data: Annotated[RpiProcessRequest | None, Body()] = None,
) -> RpiProcessResponse:
    """Baixa, lê e cruza a edição com os processos cadastrados. Sem `number`, usa a edição
    esperada pela data (a da terça mais recente). Pode levar alguns minutos.

    Os e-mails dos alertas são enviados depois da resposta, só quando o processamento dá certo.
    """
    number = data.number if data is not None else None
    try:
        result = rpi_job_service.process_now(db, number)
    # RpiNotPublishedError é subclasse de RpiDownloadError: precisa vir antes.
    except RpiNotPublishedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (RpiDownloadError, RpiParseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except RpiAlreadyProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RpiError as exc:  # RpiProcessingError
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    background.add_task(rpi_job_service.send_emails_in_new_session, session_factory)
    edition = rpi_edition_service.get_edition(db, result.edition_id)
    return RpiProcessResponse.model_validate({**asdict(result), "edition": edition}, from_attributes=True)


@router.get(
    "/editions",
    response_model=list[RpiEditionRead],
    summary="Lista as edições da RPI processadas pelo sistema (US10) — apenas perfil NIT",
    responses={403: {"description": "Usuário sem perfil NIT"}},
)
def list_rpi_editions(db: DbSession, _user: NitUser) -> Sequence[RpiEdition]:
    """Da edição mais nova para a mais antiga, sem paginação."""
    return rpi_edition_service.list_editions(db)
