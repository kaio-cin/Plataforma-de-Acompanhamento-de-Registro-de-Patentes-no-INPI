"""Download dos arquivos da RPI (US08), independente da camada HTTP e do banco.

Cada edição tem dois ZIPs no site do INPI: P<número>.zip (patentes) e PC<número>.zip (programas).
De cada um, só o XML é extraído, com nome fixo, para backend/data/rpi/<número>/.

Garantias:
- Um arquivo com o nome final está sempre completo: tudo é gravado em um temporário e só então
  renomeado (os.replace). O nome que vem dentro do ZIP nunca vira caminho no disco.
- Se um dos dois arquivos falhar, a edição inteira falha; o arquivo que deu certo fica no disco e
  não é baixado de novo na próxima tentativa.
"""

import http.client
import logging
import os
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

from app.models import AssetType
from app.services.rpi_errors import (
    RpiDownloadError,
    RpiError,
    RpiInvalidFileError,
    RpiNotPublishedError,
)

logger = logging.getLogger(__name__)

RPI_BASE_URL = "https://revistas.inpi.gov.br/txt"
# Edição não publicada: o INPI redireciona para esta página e responde 200 com HTML.
NOT_PUBLISHED_PATH = "/error/404.html"
# Identificação genérica do cliente, sem dado pessoal.
USER_AGENT = "RadarINPI/1.0"

TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (2, 4)
CHUNK_SIZE = 64 * 1024

# Limites contra arquivos anormais (o XML de patentes da RPI 2916 tem cerca de 5 MB).
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 150 * 1024 * 1024

# backend/data/rpi, independente da pasta em que o comando foi executado.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "rpi"


@dataclass(frozen=True)
class RpiFile:
    """Um dos dois arquivos de uma edição."""

    asset_type: AssetType
    zip_name: str  # modelo do nome no site, com {number}
    xml_name: str  # nome fixo do XML extraído
    label: str  # usado nas mensagens


RPI_FILES = (
    RpiFile(AssetType.PATENTE, "P{number}.zip", "patentes.xml", "patentes"),
    RpiFile(AssetType.PROGRAMA_DE_COMPUTADOR, "PC{number}.zip", "programas.xml", "programas"),
)


class _TransientError(Exception):
    """Falha passageira (rede, timeout, 5xx, HTML no lugar do ZIP): vale tentar de novo."""


class _CorruptedFileError(Exception):
    """Arquivo incompleto ou corrompido: vale tentar de novo; se persistir, vira RpiInvalidFileError."""


class _LocalDiskError(Exception):
    """Falha ao criar, gravar ou renomear arquivo no disco local: vale tentar de novo."""


def edition_dir(number: int, data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    """Pasta local da edição (guardada, relativa à pasta de dados, em RpiEdition.file_path)."""
    return data_dir / str(number)


def file_url(rpi_file: RpiFile, number: int) -> str:
    return f"{RPI_BASE_URL}/{rpi_file.zip_name.format(number=number)}"


def download_edition(number: int, data_dir: Path = DEFAULT_DATA_DIR, *, force: bool = False) -> dict[AssetType, Path]:
    """Baixa e extrai os dois XML da edição. Devolve o caminho de cada um, por tipo de ativo.

    Arquivo já existente não é baixado de novo, a menos que force=True.
    Se a edição não foi publicada, gera RpiNotPublishedError. Se um dos arquivos falhar, gera o
    erro dele depois de tentar o outro, para o que deu certo ficar no disco.
    """
    if number <= 0:
        raise ValueError(f"Número de edição inválido: {number}")

    target_dir = edition_dir(number, data_dir)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RpiDownloadError(
            f"Falha ao salvar a RPI {number}: não foi possível criar a pasta da edição no disco local."
        ) from exc

    paths: dict[AssetType, Path] = {}
    failures: list[RpiError] = []
    for rpi_file in RPI_FILES:
        destination = target_dir / rpi_file.xml_name
        if destination.exists() and not force:
            logger.info("RPI %s: arquivo de %s já existe, download ignorado.", number, rpi_file.label)
            paths[rpi_file.asset_type] = destination
            continue
        try:
            _download_with_retries(rpi_file, number, destination)
        except RpiNotPublishedError:
            # Não deixa pasta vazia para cada tentativa feita antes da publicação.
            try:
                target_dir.rmdir()
            except OSError:
                pass  # a pasta tem arquivos (de uma tentativa anterior): fica como está
            raise
        except RpiError as exc:
            logger.warning("RPI %s: falha no arquivo de %s: %s", number, rpi_file.label, exc)
            failures.append(exc)
            continue
        paths[rpi_file.asset_type] = destination

    if failures:
        raise failures[0]
    return paths


def _download_with_retries(rpi_file: RpiFile, number: int, destination: Path) -> None:
    url = file_url(rpi_file, number)
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            _download_once(url, rpi_file, number, destination)
            return
        except (_TransientError, _CorruptedFileError, _LocalDiskError) as exc:
            last_error = exc
            logger.warning(
                "RPI %s: tentativa %s de %s falhou para %s (%s)", number, attempt, MAX_ATTEMPTS, url, exc
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAYS_SECONDS[min(attempt - 1, len(RETRY_DELAYS_SECONDS) - 1)])

    if isinstance(last_error, _CorruptedFileError):
        raise RpiInvalidFileError(
            f"O arquivo de {rpi_file.label} da RPI {number} veio incompleto ou corrompido "
            f"em {MAX_ATTEMPTS} tentativas."
        ) from last_error
    if isinstance(last_error, _LocalDiskError):
        raise RpiDownloadError(
            f"Falha ao baixar ou salvar o arquivo de {rpi_file.label} da RPI {number}: "
            f"erro ao gravar no disco local em {MAX_ATTEMPTS} tentativas."
        ) from last_error
    raise RpiDownloadError(
        f"Não foi possível baixar o arquivo de {rpi_file.label} da RPI {number} após {MAX_ATTEMPTS} tentativas."
    ) from last_error


def _download_once(url: str, rpi_file: RpiFile, number: int, destination: Path) -> None:
    """Uma tentativa: baixa o ZIP para um temporário, valida e extrai o XML."""
    try:
        fd, tmp_name = tempfile.mkstemp(dir=destination.parent, prefix=".", suffix=".zip.part")
    except OSError as exc:
        raise _LocalDiskError(f"não foi possível criar o temporário ({type(exc).__name__})") from exc
    zip_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as zip_file:
            _fetch(url, rpi_file, number, zip_file)
        _extract_xml(zip_path, rpi_file, number, destination)
    finally:
        _remove_temporary(zip_path)


def _remove_temporary(path: Path) -> None:
    """Apaga um temporário. Se a limpeza falhar, só registra no log, para não esconder o erro original."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Não foi possível apagar o arquivo temporário %s (%s)", path, type(exc).__name__)


def _fetch(url: str, rpi_file: RpiFile, number: int, output: BinaryIO) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            if urlparse(response.geturl()).path == NOT_PUBLISHED_PATH:
                raise _not_published(number)
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" in content_type:
                raise _TransientError("o servidor respondeu uma página HTML no lugar do ZIP")

            expected = _content_length(response.headers.get("Content-Length"))
            received = _copy_limited(response, output, MAX_ZIP_BYTES, rpi_file, number)
            # Uma resposta cortada pode terminar sem exceção: o tamanho precisa ser conferido.
            if expected is not None and received != expected:
                raise _CorruptedFileError(f"recebidos {received} de {expected} bytes")
    # HTTPError é subclasse de URLError (e de OSError): precisa vir antes.
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise _not_published(number) from exc
        if exc.code >= 500:
            raise _TransientError(f"HTTP {exc.code}") from exc
        raise RpiDownloadError(
            f"O INPI recusou o download do arquivo de {rpi_file.label} da RPI {number} (HTTP {exc.code})."
        ) from exc
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        # Cobre falha de conexão, timeout (TimeoutError) e resposta HTTP malformada.
        # Erro de gravação no disco não chega aqui: _copy_limited o converte em _LocalDiskError.
        raise _TransientError(type(exc).__name__) from exc


def _not_published(number: int) -> RpiNotPublishedError:
    return RpiNotPublishedError(f"A RPI {number} ainda não foi publicada pelo INPI.")


def _content_length(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _copy_limited(source: BinaryIO, output: BinaryIO, limit: int, rpi_file: RpiFile, number: int) -> int:
    """Copia em blocos e interrompe se passar do limite. Devolve a quantidade de bytes copiada."""
    total = 0
    while chunk := source.read(CHUNK_SIZE):
        total += len(chunk)
        if total > limit:
            raise RpiInvalidFileError(
                f"O arquivo de {rpi_file.label} da RPI {number} passa do tamanho máximo permitido."
            )
        try:
            output.write(chunk)
        except OSError as exc:
            raise _LocalDiskError(f"falha ao gravar no disco ({type(exc).__name__})") from exc
    return total


def _extract_xml(zip_path: Path, rpi_file: RpiFile, number: int, destination: Path) -> None:
    """Valida o ZIP e grava o único XML dele em destination, de forma atômica."""
    invalid = RpiInvalidFileError(f"O arquivo de {rpi_file.label} da RPI {number} não tem o formato esperado.")
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            xml_members = [m for m in members if not m.is_dir() and m.filename.lower().endswith(".xml")]
            if len(xml_members) != 1:
                raise invalid

            # Tamanhos conferidos antes de descompactar qualquer coisa (proteção contra zip bomb).
            if any(m.file_size > MAX_MEMBER_BYTES for m in members) or (
                sum(m.file_size for m in members) > MAX_TOTAL_UNCOMPRESSED_BYTES
            ):
                raise RpiInvalidFileError(
                    f"O arquivo de {rpi_file.label} da RPI {number} passa do tamanho máximo permitido."
                )

            damaged = archive.testzip()
            if damaged is not None:
                raise _CorruptedFileError(f"membro corrompido no ZIP: {damaged}")

            fd, tmp_name = tempfile.mkstemp(dir=destination.parent, prefix=".", suffix=".xml.part")
            xml_tmp = Path(tmp_name)
            try:
                with os.fdopen(fd, "wb") as output, archive.open(xml_members[0]) as source:
                    _copy_limited(source, output, MAX_MEMBER_BYTES, rpi_file, number)
                os.replace(xml_tmp, destination)
            finally:
                _remove_temporary(xml_tmp)
    except (zipfile.BadZipFile, zlib.error, EOFError) as exc:
        raise _CorruptedFileError(f"ZIP inválido ({type(exc).__name__})") from exc
    except (NotImplementedError, RuntimeError) as exc:
        # Compressão não suportada ou arquivo protegido por senha.
        raise invalid from exc
    except OSError as exc:
        # Abrir o ZIP, criar o temporário ou renomear para o nome final (disco cheio, sem permissão,
        # arquivo bloqueado por outro programa).
        raise _LocalDiskError(f"falha no disco local ({type(exc).__name__})") from exc

    logger.info("RPI %s: XML de %s salvo em %s", number, rpi_file.label, destination)
