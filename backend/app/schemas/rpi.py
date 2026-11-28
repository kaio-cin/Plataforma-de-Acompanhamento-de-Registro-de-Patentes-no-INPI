from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AssetType, RpiEditionStatus


class RpiProcessRequest(BaseModel):
    """Pedido do botão "Processar agora". Sem número, processa a edição esperada pela data."""

    number: int | None = Field(default=None, ge=1, le=99999, description="Número da RPI (ex.: 2917)")


class RpiEditionRead(BaseModel):
    """Edição da RPI como a tela de edições recebe (US10).

    Só saída: herda direto de BaseModel, sem limites de tamanho nem validadores, para um dado
    antigo ou fora das regras atuais não derrubar a lista inteira (ver DT-13).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    publication_date: date
    status: RpiEditionStatus
    dispatch_count: int
    error_message: str | None
    processed_at: datetime | None  # última mudança de status, em UTC sem indicação de fuso


class UnknownCodeRead(BaseModel):
    """Código de despacho cruzado que não está no glossário."""

    model_config = ConfigDict(from_attributes=True)

    asset_type: AssetType
    code: str
    count: int


class RpiProcessResponse(BaseModel):
    """Resumo do processamento de uma edição (resposta do botão "Processar agora")."""

    model_config = ConfigDict(from_attributes=True)

    edition: RpiEditionRead
    total_in_rpi: int
    skipped_by_parser: int
    matched: int
    new_dispatches: int
    existing_dispatches: int
    alerts_created: int
    unknown_codes: list[UnknownCodeRead]
    type_mismatches: list[str]
    ambiguous_processes: list[str]
    duplicates_in_rpi: int
