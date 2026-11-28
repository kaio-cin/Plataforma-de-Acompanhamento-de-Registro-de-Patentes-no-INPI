"""Códigos de despacho do INPI carregados no glossário (tabela dispatch_codes).

Só dados: a validação e a carga ficam em app/seed_codes.py (python -m app.seed_codes).

Como preencher cada código:
- official_description: texto exato da fonte oficial registrada em FONTE, sem resumir.
- plain_description: explicação em linguagem simples para quem não é técnico, escrita pela equipe.
- requires_action: True quando, se ninguém agir, o ativo é prejudicado (arquivamento, indeferimento
  definitivo, extinção) ou se perde a única chance de reverter uma decisão contra ele.
- deadline_days: só quando a fonte dá o prazo em dias corridos, contado da publicação na RPI e sem
  condição, e apenas em código que exige ação. Prazo em meses, em dias úteis, condicional ou contado
  de outro marco fica vazio (None) e é explicado no plain_description. Comente a linha nesses casos.

Nunca invente código, descrição oficial ou prazo: tudo vem da fonte registrada em FONTE.
"""

from dataclasses import dataclass
from datetime import date

from app.models.enums import AssetType


@dataclass(frozen=True)
class DispatchCodeEntry:
    """Um código de despacho como será gravado em dispatch_codes."""

    asset_type: AssetType
    code: str  # como publicado na RPI (ex.: "6.1"), sem espaços
    official_description: str
    plain_description: str
    requires_action: bool = False
    deadline_days: int | None = None  # dias corridos a partir da publicação; None sem prazo claro


@dataclass(frozen=True)
class FonteOficial:
    """De onde vieram os códigos de uma seção da RPI. None indica informação ainda pendente."""

    titulo: str | None = None
    url: str | None = None
    versao: str | None = None  # versão ou data do próprio documento
    data_consulta: date | None = None


# Fonte de cada seção, registrada separadamente. PENDENTE: preencher quando a tabela oficial for entregue.
FONTE: dict[AssetType, FonteOficial] = {
    AssetType.PATENTE: FonteOficial(),
    AssetType.PROGRAMA_DE_COMPUTADOR: FonteOficial(),
}

# PENDENTE: vazia até a tabela oficial do INPI ser entregue.
DISPATCH_CODES: tuple[DispatchCodeEntry, ...] = ()
