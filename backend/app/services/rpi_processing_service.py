"""Processamento de uma edição da RPI (US09): baixa, lê, cruza com os ativos e grava despachos e alertas.

Fluxo e transações:

1. Checagem inicial: se a edição está em "Processando" dentro do tempo-limite, desiste antes de baixar.
   A transação é encerrada (rollback) antes do download, que pode demorar.
2. Download e parse, sem tocar no banco. Se falharem, a falha só é registrada numa edição que já
   existe e não está ocupada (um único UPDATE condicional). Edição nova não é gravada: a data de
   publicação, obrigatória, vem do XML. Edição não publicada nunca grava nada.
3. Reserva (commit): a edição passa a "Processando". Só uma chamada consegue a reserva, mesmo com
   o agendamento e o botão "Processar agora" rodando juntos.
4. Cruzamento: despachos novos, vínculo com o glossário e alertas. Um único commit grava tudo com o
   status "Processada". Em falha: rollback e, separadamente, status "Erro".

O service faz commit e rollback na sessão recebida: quem chama deve passar uma sessão sem
alterações pendentes. Os e-mails dos alertas NÃO são enviados aqui; quem chama faz isso depois.

Todas as datas são gravadas e comparadas em UTC sem fuso, como nos demais models.
"""

import logging
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, AssetType, Dispatch, DispatchCode, RpiEdition, RpiEditionStatus
from app.models.limits import RPI_ERROR_MESSAGE_MAX_LENGTH
from app.services import alert_service, rpi_download_service, rpi_parser
from app.services.process_number import has_known_format, normalize_process_number
from app.services.rpi_errors import (
    RpiAlreadyProcessingError,
    RpiError,
    RpiNotPublishedError,
    RpiProcessingError,
)
from app.services.rpi_parser import ParsedEdition

logger = logging.getLogger(__name__)

# Depois desse tempo, uma edição presa em "Processando" (processo que caiu) pode ser retomada.
PROCESSING_TIMEOUT = timedelta(minutes=10)


def _utc_now() -> datetime:
    # UTC sem fuso, como as demais colunas DateTime do projeto (ver models/alert.py).
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class UnknownCode:
    """Código de despacho cruzado que não está no glossário."""

    asset_type: AssetType
    code: str
    count: int  # despachos cruzados com esse código nesta execução


@dataclass(frozen=True)
class ProcessingResult:
    """Resumo do processamento de uma edição, para a rota e para o log."""

    edition_id: int
    number: int
    publication_date: date
    total_in_rpi: int  # despachos lidos do XML
    skipped_by_parser: int
    matched: int  # despachos do XML que cruzaram com um ativo (= novos + existentes)
    new_dispatches: int
    existing_dispatches: int  # já gravados por um processamento anterior
    dispatch_count: int  # total gravado da edição (= RpiEdition.dispatch_count)
    alerts_created: int
    unknown_codes: tuple[UnknownCode, ...]
    type_mismatches: tuple[str, ...]  # processos cujo ativo tem tipo diferente da seção da RPI
    ambiguous_processes: tuple[str, ...]  # número normalizado igual em mais de um ativo
    duplicates_in_rpi: int  # pares (processo, código) repetidos no XML, ignorados


def process_edition(
    db: Session,
    number: int,
    *,
    data_dir: Path = rpi_download_service.DEFAULT_DATA_DIR,
    force_download: bool = False,
    now: Callable[[], datetime] = _utc_now,
) -> ProcessingResult:
    """Processa a edição `number` da RPI e devolve o resumo.

    force_download=True baixa os XML de novo (por exemplo, quando o arquivo salvo falhou no parse).

    Erros (mensagens em português): RpiNotPublishedError, RpiDownloadError, RpiInvalidFileError,
    RpiParseError, RpiAlreadyProcessingError e RpiProcessingError.
    """
    if number <= 0:
        raise ValueError(f"Número de edição inválido: {number}")

    # 1. Checagem inicial, sem segurar a transação durante o download.
    try:
        current = db.execute(
            select(RpiEdition.status, RpiEdition.processed_at).where(RpiEdition.number == number)
        ).one_or_none()
        db.rollback()
    except SQLAlchemyError as exc:
        raise _start_failed(db, number) from exc
    if current is not None and _is_locked(current.status, current.processed_at, now()):
        raise _already_processing(number)

    # 2. Download e parse.
    try:
        paths = rpi_download_service.download_edition(number, data_dir, force=force_download)
        parsed = rpi_parser.parse_edition(paths, number)
    except RpiNotPublishedError:
        raise
    except RpiError as exc:
        _record_failure_before_claim(db, number, str(exc), now())
        raise

    # 3. Reserva.
    claimed_at = now()
    try:
        edition_id = _claim(db, number, parsed.publication_date, claimed_at)
    except SQLAlchemyError as exc:
        # Sem reserva, esta chamada não grava "Erro" na edição.
        raise _start_failed(db, number) from exc

    # 4. Cruzamento e gravação.
    try:
        edition = db.scalars(
            select(RpiEdition).where(RpiEdition.id == edition_id).execution_options(populate_existing=True)
        ).one()
        if edition.publication_date != parsed.publication_date:
            raise RpiProcessingError(
                f"A data de publicação da RPI {number} no arquivo ({parsed.publication_date:%d/%m/%Y}) é "
                f"diferente da registrada ({edition.publication_date:%d/%m/%Y})."
            )
        result = _cross(db, edition, parsed)
        edition.status = RpiEditionStatus.PROCESSADA
        edition.dispatch_count = result.dispatch_count
        edition.error_message = None
        edition.file_path = str(number)
        edition.processed_at = now()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("RPI %s: falha no cruzamento com os processos cadastrados.", number)
        message = str(exc) if isinstance(exc, RpiError) else _processing_failed_message(number)
        _record_failure_after_claim(db, edition_id, claimed_at, message, now())
        if isinstance(exc, RpiError):
            raise
        raise RpiProcessingError(message) from exc

    logger.info(
        "RPI %s processada: %s despachos lidos, %s cruzados (%s novos), %s alertas criados.",
        number,
        result.total_in_rpi,
        result.matched,
        result.new_dispatches,
        result.alerts_created,
    )
    return result


# --- Status e reserva ------------------------------------------------------------------------------------------------


def _is_locked(status: RpiEditionStatus, processed_at: datetime | None, moment: datetime) -> bool:
    """Edição em "Processando" há menos que o tempo-limite: outra chamada está trabalhando nela."""
    return (
        status == RpiEditionStatus.PROCESSANDO
        and processed_at is not None
        and processed_at >= moment - PROCESSING_TIMEOUT
    )


def _stale_processing(moment: datetime):
    """Condição SQL: "Processando" parado há mais que o tempo-limite (ou sem data)."""
    return and_(
        RpiEdition.status == RpiEditionStatus.PROCESSANDO,
        or_(RpiEdition.processed_at.is_(None), RpiEdition.processed_at < moment - PROCESSING_TIMEOUT),
    )


def _already_processing(number: int) -> RpiAlreadyProcessingError:
    return RpiAlreadyProcessingError(f"A RPI {number} já está sendo processada. Tente de novo em alguns minutos.")


def _start_failed(db: Session, number: int) -> RpiProcessingError:
    """Falha de banco antes de obter a reserva (ex.: "database is locked"): desfaz e devolve o erro do service.

    Chamada dentro do bloco except, para o logger.exception registrar a causa técnica.
    """
    logger.exception("RPI %s: falha no banco ao iniciar o processamento.", number)
    try:
        db.rollback()
    except SQLAlchemyError:
        logger.exception("RPI %s: falha também no rollback.", number)
    return RpiProcessingError(
        f"Não foi possível iniciar o processamento da RPI {number}. Tente de novo em alguns minutos."
    )


def _processing_failed_message(number: int) -> str:
    return f"Falha ao cruzar a RPI {number} com os processos cadastrados. Tente processar de novo."


def _claim(db: Session, number: int, publication_date: date, moment: datetime) -> int:
    """Reserva a edição para esta chamada (status "Processando", com commit) e devolve o id.

    Edição existente: UPDATE condicional, atômico no banco. Edição nova: INSERT, protegido pela
    unicidade do número; se outra chamada inseriu antes, tenta uma vez o caminho da existente.
    """
    for _ in range(2):
        edition_id = db.scalar(select(RpiEdition.id).where(RpiEdition.number == number))
        if edition_id is None:
            edition = RpiEdition(
                number=number,
                publication_date=publication_date,
                status=RpiEditionStatus.PROCESSANDO,
                file_path=str(number),
                processed_at=moment,
            )
            db.add(edition)
            try:
                db.flush()
                new_id = edition.id
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            return new_id

        result = db.execute(
            update(RpiEdition)
            .where(
                RpiEdition.id == edition_id,
                or_(RpiEdition.status != RpiEditionStatus.PROCESSANDO, _stale_processing(moment)),
            )
            .values(status=RpiEditionStatus.PROCESSANDO, processed_at=moment, error_message=None)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if result.rowcount == 1:
            return edition_id
        raise _already_processing(number)
    raise _already_processing(number)


def _truncate(message: str) -> str:
    if len(message) <= RPI_ERROR_MESSAGE_MAX_LENGTH:
        return message
    return message[: RPI_ERROR_MESSAGE_MAX_LENGTH - 1] + "…"


def _record_failure_before_claim(db: Session, number: int, message: str, moment: datetime) -> None:
    """Registra a falha do download ou do parse, sem nunca ler o status antes de gravar.

    Um único UPDATE condicional: só muda a edição se ela estiver em "Erro", em "Baixada" ou presa
    em "Processando" além do tempo-limite. "Processada" e "Processando" recente ficam intactas.
    Edição inexistente não é criada (a data de publicação é desconhecida).
    """
    try:
        result = db.execute(
            update(RpiEdition)
            .where(
                RpiEdition.number == number,
                or_(
                    RpiEdition.status.in_([RpiEditionStatus.ERRO, RpiEditionStatus.BAIXADA]),
                    _stale_processing(moment),
                ),
            )
            .values(status=RpiEditionStatus.ERRO, error_message=_truncate(message), processed_at=moment)
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("RPI %s: não foi possível registrar a falha na edição.", number)
        return
    if result.rowcount == 0:
        logger.warning(
            "RPI %s: falha não registrada na edição (inexistente, já processada ou em processamento): %s",
            number,
            message,
        )


def _record_failure_after_claim(
    db: Session, edition_id: int, claimed_at: datetime, message: str, moment: datetime
) -> None:
    """Grava "Erro" na edição reservada por esta chamada, depois do rollback do cruzamento.

    Só altera se a reserva ainda é desta chamada (mesmo processed_at): se outra chamada retomou a
    edição depois do tempo-limite, o trabalho dela não é sobrescrito. Uma falha aqui só vai para o
    log, para não esconder o erro original.
    """
    try:
        result = db.execute(
            update(RpiEdition)
            .where(
                RpiEdition.id == edition_id,
                RpiEdition.status == RpiEditionStatus.PROCESSANDO,
                RpiEdition.processed_at == claimed_at,
            )
            .values(status=RpiEditionStatus.ERRO, error_message=_truncate(message), processed_at=moment)
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Não foi possível registrar o erro na edição %s da RPI.", edition_id)
        return
    if result.rowcount == 0:
        logger.warning("Edição %s da RPI: o erro não foi registrado, a reserva já não era desta chamada.", edition_id)


# --- Cruzamento ------------------------------------------------------------------------------------------------------


def _choose_asset(candidates: list[Asset], asset_type: AssetType) -> Asset:
    """Entre ativos com o mesmo número normalizado: primeiro os do tipo da seção, depois o menor id."""
    same_type = [asset for asset in candidates if asset.asset_type == asset_type]
    return min(same_type or candidates, key=lambda asset: asset.id)


def _load_assets(db: Session) -> dict[str, list[Asset]]:
    """Todos os ativos, indexados pelo número normalizado (uma consulta só)."""
    by_key: dict[str, list[Asset]] = defaultdict(list)
    unusual: list[str] = []
    for asset in db.scalars(select(Asset).options(selectinload(Asset.author_user)).order_by(Asset.id)):
        key = normalize_process_number(asset.process_number)
        by_key[key].append(asset)
        if not has_known_format(key):
            unusual.append(asset.process_number)
    if unusual:
        logger.warning(
            "%s ativo(s) com número fora dos formatos da RPI (BR + 13 dígitos, PI ou MU + 8 dígitos); "
            "eles não vão cruzar com os despachos: %s",
            len(unusual),
            ", ".join(unusual),
        )
    return by_key


def _cross(db: Session, edition: RpiEdition, parsed: ParsedEdition) -> ProcessingResult:
    assets_by_key = _load_assets(db)
    glossary = {(code.asset_type, code.code): code for code in db.scalars(select(DispatchCode))}
    existing = {
        (dispatch.process_number, dispatch.code): dispatch
        for dispatch in db.scalars(
            select(Dispatch).options(selectinload(Dispatch.asset)).where(Dispatch.edition_id == edition.id)
        )
    }

    seen: set[tuple[str, str]] = set()
    new_count = existing_count = alerts_created = duplicates = 0
    unknown: Counter[tuple[AssetType, str]] = Counter()
    # dict como conjunto ordenado: cada processo aparece uma vez, na ordem da RPI.
    ambiguous: dict[str, str] = {}
    mismatches: dict[str, str] = {}

    for parsed_dispatch in parsed.dispatches:
        key = normalize_process_number(parsed_dispatch.process_number)
        candidates = assets_by_key.get(key)
        if not candidates:
            continue

        pair = (parsed_dispatch.process_number, parsed_dispatch.code)
        if pair in seen:
            duplicates += 1
            logger.warning(
                "RPI %s: despacho %s do processo %s repetido no XML; só o primeiro foi considerado.",
                parsed.number,
                parsed_dispatch.code,
                parsed_dispatch.process_number,
            )
            continue
        seen.add(pair)

        code = glossary.get((parsed_dispatch.asset_type, parsed_dispatch.code))
        dispatch = existing.get(pair)
        if dispatch is not None:
            existing_count += 1
            # Glossário carregado depois do primeiro processamento: preenche só o vínculo vazio.
            if dispatch.dispatch_code_id is None and code is not None:
                dispatch.dispatch_code = code
            asset = dispatch.asset  # nunca troca o ativo de um despacho já gravado
        else:
            asset = _choose_asset(candidates, parsed_dispatch.asset_type)
            dispatch = Dispatch(
                edition_id=edition.id,
                asset=asset,
                process_number=parsed_dispatch.process_number,
                code=parsed_dispatch.code,
                dispatch_code=code,
                description=parsed_dispatch.description,
                complement=parsed_dispatch.complement,
                publication_date=parsed.publication_date,
            )
            db.add(dispatch)
            alerts_created += len(alert_service.create_alerts_for(db, dispatch))
            new_count += 1

        if len(candidates) > 1 and key not in ambiguous:
            ambiguous[key] = parsed_dispatch.process_number
            logger.warning(
                "RPI %s: o processo %s corresponde a %s ativos cadastrados; despacho ligado ao ativo %s.",
                parsed.number,
                parsed_dispatch.process_number,
                len(candidates),
                asset.id,
            )
        if asset.asset_type != parsed_dispatch.asset_type and key not in mismatches:
            mismatches[key] = parsed_dispatch.process_number
            logger.warning(
                "RPI %s: o processo %s aparece na seção de %s, mas o ativo %s está cadastrado como %s.",
                parsed.number,
                parsed_dispatch.process_number,
                parsed_dispatch.asset_type.value,
                asset.id,
                asset.asset_type.value,
            )
        if code is None:
            unknown[(parsed_dispatch.asset_type, parsed_dispatch.code)] += 1

    for (asset_type, code_text), count in unknown.items():
        logger.warning(
            "RPI %s: código %s (%s) fora do glossário em %s despacho(s) cruzado(s).",
            parsed.number,
            code_text,
            asset_type.value,
            count,
        )

    db.flush()
    dispatch_count = db.scalar(select(func.count()).select_from(Dispatch).where(Dispatch.edition_id == edition.id))

    return ProcessingResult(
        edition_id=edition.id,
        number=parsed.number,
        publication_date=parsed.publication_date,
        total_in_rpi=len(parsed.dispatches),
        skipped_by_parser=parsed.skipped,
        matched=new_count + existing_count,
        new_dispatches=new_count,
        existing_dispatches=existing_count,
        dispatch_count=dispatch_count,
        alerts_created=alerts_created,
        unknown_codes=tuple(
            UnknownCode(asset_type=asset_type, code=code_text, count=count)
            for (asset_type, code_text), count in unknown.items()
        ),
        type_mismatches=tuple(mismatches.values()),
        ambiguous_processes=tuple(ambiguous.values()),
        duplicates_in_rpi=duplicates,
    )
