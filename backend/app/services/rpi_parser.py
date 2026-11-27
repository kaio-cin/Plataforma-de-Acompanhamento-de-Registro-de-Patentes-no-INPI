"""Leitura do XML da RPI (US09): extrai os despachos, sem rede, sem banco e sem schemas HTTP.

Formato (RPI 2916):

    <revista numero="2916" dataPublicacao="24/11/2026" diretoria="Patente|Programa">
      <despacho>
        <codigo>6.1</codigo>
        <titulo>Exigência Técnica</titulo>
        <processo-patente> (ou <processo-programa>)
          <numero>BR 10 2023 001234-5</numero>
          ...
        </processo-patente>
        <comentario>...</comentario>   (opcional)
      </despacho>
    </revista>

Só valem os filhos DIRETOS de <despacho> e do processo: há <titulo>, <codigo> e <numero> aninhados
em outros blocos (título do pedido, campo de aplicação, divisão de pedido, pedido principal).

Problemas no arquivo inteiro geram RpiParseError. Um despacho incompleto é ignorado com aviso no
log e contado em `skipped`, para não perder os demais.
"""

import io
import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.models import AssetType
from app.models.limits import (
    DISPATCH_CODE_MAX_LENGTH,
    DISPATCH_DESCRIPTION_MAX_LENGTH,
    PROCESS_NUMBER_MAX_LENGTH,
)
from app.services.rpi_errors import RpiParseError

logger = logging.getLogger(__name__)

ROOT_TAG = "revista"
DISPATCH_TAG = "despacho"
DATE_FORMAT = "%d/%m/%Y"
ELLIPSIS = "…"

DIRECTORATES = {
    "Patente": AssetType.PATENTE,
    "Programa": AssetType.PROGRAMA_DE_COMPUTADOR,
}
PROCESS_TAGS = {
    AssetType.PATENTE: "processo-patente",
    AssetType.PROGRAMA_DE_COMPUTADOR: "processo-programa",
}
LABELS = {
    AssetType.PATENTE: "patentes",
    AssetType.PROGRAMA_DE_COMPUTADOR: "programas",
}

_XML_DECLARATION_ENCODING = re.compile(r"""^\s*<\?xml[^>]*\bencoding\s*=\s*["']([^"']+)["']""")


@dataclass(frozen=True)
class ParsedDispatch:
    """Um despacho como veio na RPI. Ainda não cruzado com os ativos."""

    asset_type: AssetType  # revista@diretoria
    process_number: str  # processo/numero (filho direto), só sem espaços nas pontas
    code: str  # despacho/codigo
    description: str  # despacho/titulo
    complement: str | None  # despacho/comentario, None se ausente ou vazio


@dataclass(frozen=True)
class ParsedRpiFile:
    """Um dos arquivos da edição (patentes ou programas)."""

    number: int  # revista@numero
    publication_date: date  # revista@dataPublicacao
    asset_type: AssetType  # revista@diretoria
    dispatches: tuple[ParsedDispatch, ...]
    skipped: int  # despachos ignorados com aviso no log


@dataclass(frozen=True)
class ParsedEdition:
    """A edição completa: patentes seguidas de programas."""

    number: int
    publication_date: date
    dispatches: tuple[ParsedDispatch, ...]
    skipped: int


def parse_edition(paths: Mapping[AssetType, Path], expected_number: int) -> ParsedEdition:
    """Lê os dois XML de uma edição (o formato devolvido por download_edition) e junta os despachos.

    Exige exatamente um arquivo de patentes e um de programas, cada um com a diretoria
    correspondente, o número esperado e a mesma data de publicação.
    """
    if set(paths) != set(PROCESS_TAGS):
        raise RpiParseError(
            f"A RPI {expected_number} precisa de exatamente um arquivo de patentes e um de programas."
        )

    parsed: list[ParsedRpiFile] = []
    for asset_type in PROCESS_TAGS:  # ordem fixa: patentes, depois programas
        rpi_file = parse_rpi_file(paths[asset_type])
        label = LABELS[asset_type]
        if rpi_file.asset_type != asset_type:
            raise RpiParseError(
                f"O arquivo de {label} da RPI {expected_number} contém despachos de {LABELS[rpi_file.asset_type]}."
            )
        if rpi_file.number != expected_number:
            raise RpiParseError(
                f"O arquivo de {label} é da RPI {rpi_file.number}, mas era esperada a RPI {expected_number}."
            )
        parsed.append(rpi_file)

    if len({f.publication_date for f in parsed}) != 1:
        raise RpiParseError(f"Os arquivos da RPI {expected_number} têm datas de publicação diferentes.")

    return ParsedEdition(
        number=expected_number,
        publication_date=parsed[0].publication_date,
        dispatches=tuple(d for f in parsed for d in f.dispatches),
        skipped=sum(f.skipped for f in parsed),
    )


def parse_rpi_file(source: Path | bytes) -> ParsedRpiFile:
    """Lê um XML da RPI (caminho ou conteúdo) e devolve os despachos encontrados."""
    name = source.name if isinstance(source, Path) else "XML"
    if isinstance(source, Path):
        try:
            raw = source.read_bytes()
        except OSError as exc:
            # Arquivo ausente, sem permissão ou ilegível.
            raise RpiParseError(f"Não foi possível ler o arquivo {name} da RPI.") from exc
    else:
        raw = source
    _check_safe_utf8(raw, name)

    header: tuple[int, date, AssetType] | None = None
    dispatches: list[ParsedDispatch] = []
    skipped = 0
    depth = 0
    root: ET.Element | None = None

    # iterparse + clear(): cada <despacho> é descartado depois de lido, sem montar a árvore inteira.
    try:
        for event, elem in ET.iterparse(io.BytesIO(raw), events=("start", "end")):
            if event == "start":
                depth += 1
                if depth == 1:
                    root = elem
                    header = _read_header(elem, name)
                continue

            depth -= 1
            if depth == 1 and elem.tag == DISPATCH_TAG and header is not None:
                dispatch = _read_dispatch(elem, header[2], header[0])
                if dispatch is None:
                    skipped += 1
                else:
                    dispatches.append(dispatch)
                elem.clear()
                if root is not None:
                    root.clear()
    except ET.ParseError as exc:
        raise RpiParseError(f"O arquivo {name} está corrompido ou não é um XML válido.") from exc

    if header is None:  # pragma: no cover - o ParseError acima cobre o arquivo vazio
        raise RpiParseError(f"O arquivo {name} está vazio.")

    number, publication_date, asset_type = header
    if not dispatches:
        logger.warning("RPI %s: o arquivo de %s não tem despachos.", number, LABELS[asset_type])

    return ParsedRpiFile(
        number=number,
        publication_date=publication_date,
        asset_type=asset_type,
        dispatches=tuple(dispatches),
        skipped=skipped,
    )


def _check_safe_utf8(raw: bytes, name: str) -> None:
    """Exige UTF-8 válido e recusa DOCTYPE/ENTITY (a RPI real não usa).

    Sem exigir UTF-8, outra codificação (UTF-16, por exemplo) esconderia o DOCTYPE da checagem.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RpiParseError(f"O arquivo {name} não está em UTF-8.") from exc
    # Caractere nulo indica UTF-16/32 lido como UTF-8.
    if "\x00" in text:
        raise RpiParseError(f"O arquivo {name} não está em UTF-8.")
    declared = _XML_DECLARATION_ENCODING.match(text.lstrip("\ufeff"))
    if declared and declared.group(1).lower().replace("_", "-") not in ("utf-8", "utf8"):
        raise RpiParseError(f"O arquivo {name} não está em UTF-8.")
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise RpiParseError(f"O arquivo {name} tem uma declaração DOCTYPE, que a RPI não usa.")


def _read_header(root: ET.Element, name: str) -> tuple[int, date, AssetType]:
    if root.tag != ROOT_TAG:
        raise RpiParseError(f"O arquivo {name} não é uma RPI: a raiz é <{root.tag}>, e não <{ROOT_TAG}>.")

    raw_number = (root.get("numero") or "").strip()
    try:
        number = int(raw_number)
    except ValueError:
        raise RpiParseError(f"O arquivo {name} tem número de edição inválido: '{raw_number}'.") from None
    if number <= 0:
        raise RpiParseError(f"O arquivo {name} tem número de edição inválido: '{raw_number}'.")

    raw_date = (root.get("dataPublicacao") or "").strip()
    try:
        publication_date = datetime.strptime(raw_date, DATE_FORMAT).date()
    except ValueError:
        raise RpiParseError(f"A RPI {number} tem data de publicação inválida: '{raw_date}'.") from None

    directorate = (root.get("diretoria") or "").strip()
    if directorate not in DIRECTORATES:
        raise RpiParseError(f"A RPI {number} tem diretoria desconhecida: '{directorate}'.")

    return number, publication_date, DIRECTORATES[directorate]


def _read_dispatch(elem: ET.Element, asset_type: AssetType, number: int) -> ParsedDispatch | None:
    """Lê um <despacho>. Devolve None (com aviso no log) se faltar algo essencial."""
    # find() com nome simples só procura entre os filhos diretos.
    process = elem.find(PROCESS_TAGS[asset_type])
    process_number = (process.findtext("numero") or "").strip() if process is not None else ""
    code = _clean(elem.findtext("codigo"))
    where = f"RPI {number}, processo '{process_number or '?'}'"

    if not process_number:
        logger.warning("%s: despacho sem número de processo ignorado.", where)
        return None
    if len(process_number) > PROCESS_NUMBER_MAX_LENGTH:
        logger.warning("%s: número de processo longo demais, despacho ignorado.", where)
        return None
    if not code:
        logger.warning("%s: despacho sem código ignorado.", where)
        return None
    if len(code) > DISPATCH_CODE_MAX_LENGTH:
        logger.warning("%s: código '%s' longo demais, despacho ignorado.", where, code[:20])
        return None

    description = _clean(elem.findtext("titulo"))
    if not description:
        logger.warning("%s: despacho %s sem título; usado um texto padrão.", where, code)
        description = f"Despacho {code}"
    if len(description) > DISPATCH_DESCRIPTION_MAX_LENGTH:
        logger.warning("%s: título do despacho %s cortado.", where, code)
        description = description[: DISPATCH_DESCRIPTION_MAX_LENGTH - len(ELLIPSIS)] + ELLIPSIS

    return ParsedDispatch(
        asset_type=asset_type,
        process_number=process_number,
        code=code,
        description=description,
        complement=_clean(elem.findtext("comentario")) or None,
    )


def _clean(text: str | None) -> str:
    """Tira espaços das pontas e reduz espaços internos a um só."""
    return " ".join(text.split()) if text else ""
