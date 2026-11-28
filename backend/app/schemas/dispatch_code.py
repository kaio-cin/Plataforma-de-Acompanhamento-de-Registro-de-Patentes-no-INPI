from pydantic import BaseModel, ConfigDict

from app.models.enums import AssetType


class DispatchCodeRead(BaseModel):
    """Código de despacho como o glossário do front-end recebe.

    Só saída: herda direto de BaseModel, sem limites de tamanho nem validadores, para um dado
    antigo ou fora das regras atuais não derrubar a lista inteira (ver DT-13).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    asset_type: AssetType
    official_description: str
    plain_description: str
    requires_action: bool
    deadline_days: int | None
