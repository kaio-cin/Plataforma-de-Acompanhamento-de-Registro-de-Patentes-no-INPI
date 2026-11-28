import re
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import AssetType
from app.models.limits import (
    AUTHORS_MAX_LENGTH,
    AUTHORS_MIN_LENGTH,
    PROCESS_NUMBER_MAX_LENGTH,
    PROCESS_NUMBER_MIN_LENGTH,
    STATUS_MAX_LENGTH,
    STATUS_MIN_LENGTH,
    TITLE_MAX_LENGTH,
    TITLE_MIN_LENGTH,
)


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class AssetBase(BaseModel):
    title: str = Field(
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
        examples=["Sistema de irrigação automatizada por sensores"],
    )
    asset_type: AssetType = Field(examples=[AssetType.PATENTE])
    process_number: str = Field(
        min_length=PROCESS_NUMBER_MIN_LENGTH,
        max_length=PROCESS_NUMBER_MAX_LENGTH,
        examples=["BR 10 2023 001234-5"],
    )
    deposit_date: date = Field(examples=["2023-03-12"])
    status: str = Field(min_length=STATUS_MIN_LENGTH, max_length=STATUS_MAX_LENGTH, examples=["Em exame"])
    authors: str = Field(
        min_length=AUTHORS_MIN_LENGTH,
        max_length=AUTHORS_MAX_LENGTH,
        description="Inventores/autores separados por vírgula.",
        examples=["Fernanda Lima Costa, Rodrigo A. Nascimento"],
    )

    @field_validator("title", "status", "authors")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _collapse_spaces(value)

    @field_validator("process_number")
    @classmethod
    def _normalize_process_number(cls, value: str) -> str:
        # Padroniza para casar com o número publicado na RPI: maiúsculas e espaços simples.
        return _collapse_spaces(value).upper()


class AssetCreate(AssetBase):
    author_email: EmailStr | None = Field(
        default=None,
        description="E-mail de um usuário AUTOR já cadastrado, para dar a ele acesso de acompanhamento (US07).",
        examples=["fernanda.costa@instituicao.edu.br"],
    )

    @field_validator("deposit_date")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("A data de depósito não pode estar no futuro.")
        return value

    @field_validator("author_email", mode="before")
    @classmethod
    def _empty_email_as_none(cls, value: object) -> object:
        # O formulário do frontend envia "" quando o campo opcional fica em branco.
        if isinstance(value, str) and not value.strip():
            return None
        return value


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_user_id: int | None
    author_email: EmailStr | None


class AssetUpdate(AssetCreate):
    """Dados da edição de um ativo (US05): substitui todos os campos, com as mesmas regras do cadastro.

    author_email é obrigatório para não remover o autor sem querer: quem esquecer o campo recebe 422.
    null ou "" removem o vínculo de propósito.
    """

    author_email: EmailStr | None = Field(
        description=(
            "E-mail de um usuário AUTOR já cadastrado. Obrigatório: envie null ou \"\" para remover o autor vinculado."
        ),
        examples=["fernanda.costa@instituicao.edu.br"],
    )
