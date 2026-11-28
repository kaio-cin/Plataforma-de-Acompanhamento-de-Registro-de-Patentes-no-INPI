"""Configurações da aplicação, lidas de variáveis de ambiente ou do arquivo .env."""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Radar INPI — Acompanhamento de PI no INPI"
    api_prefix: str = "/api"

    # SQLite no desenvolvimento. Para PostgreSQL, basta trocar a URL:
    # postgresql://usuario:senha@host:5432/pi_inpi (o driver psycopg é escolhido automaticamente)
    database_url: str = "sqlite:///./pi_inpi.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def _postgres_driver(cls, value: object) -> object:
        # Serviços de hospedagem (ex.: Render) fornecem "postgres://" ou "postgresql://", sem driver;
        # o SQLAlchemy precisa de "postgresql+psycopg://" para usar o psycopg 3.
        if isinstance(value, str):
            value = value.strip()
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    # JWT — em produção, defina JWT_SECRET_KEY no .env com um valor longo e aleatório.
    jwt_secret_key: str = "dev-secret-troque-em-producao"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    # Origens (frontends) autorizadas a chamar a API pelo navegador.
    # No .env: CORS_ORIGINS=http://localhost:5173,https://radar.instituicao.edu.br
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        # Aceita lista separada por vírgulas; remove espaços e barra final ("http://x/" == "http://x").
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list):
            return [str(origin).strip().rstrip("/") for origin in value if str(origin).strip()]
        return value

    # E-mail dos alertas (US11). Com SMTP_HOST vazio, o e-mail só é impresso no terminal
    # (desenvolvimento). Preenchido, é enviado por SMTP (ex.: Gmail com senha de app ou Mailtrap).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
