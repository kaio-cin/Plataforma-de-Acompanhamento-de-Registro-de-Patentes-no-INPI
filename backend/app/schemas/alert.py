from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    """Alerta como o front-end recebe (US12).

    Só saída: herda direto de BaseModel, sem limites de tamanho nem validadores, para um dado
    antigo ou fora das regras atuais não derrubar a lista inteira (ver DT-13).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    asset_title: str
    process_number: str
    dispatch_code: str
    dispatch_description: str
    dispatch_plain_description: str | None
    publication_date: date
    requires_action: bool
    deadline: date | None
    is_read: bool
    created_at: datetime


class UnreadCount(BaseModel):
    """Quantidade de alertas não lidos, para o contador da barra superior."""

    count: int
