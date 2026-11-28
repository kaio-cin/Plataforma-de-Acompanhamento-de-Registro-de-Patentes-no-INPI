"""Suporte a PostgreSQL sem precisar de um servidor: URL do banco, driver e SQL das tabelas."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.core.config import Settings
from app.database import Base


def _database_url(value: str) -> str:
    return Settings(database_url=value, _env_file=None).database_url


@pytest.mark.parametrize(
    ("informada", "usada"),
    [
        # Formatos fornecidos por serviços de hospedagem, sem driver.
        ("postgres://u:s@host:5432/radar", "postgresql+psycopg://u:s@host:5432/radar"),
        ("postgresql://u:s@host:5432/radar", "postgresql+psycopg://u:s@host:5432/radar"),
        ("  postgresql://u:s@host/radar\n", "postgresql+psycopg://u:s@host/radar"),
        # Já com driver ou outro banco: fica como está.
        ("postgresql+psycopg://u:s@host/radar", "postgresql+psycopg://u:s@host/radar"),
        ("sqlite:///./pi_inpi.db", "sqlite:///./pi_inpi.db"),
    ],
)
def test_url_do_postgresql_usa_o_driver_psycopg(informada: str, usada: str) -> None:
    assert _database_url(informada) == usada


def test_url_lida_do_ambiente_tambem_e_convertida(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://u:s@host/radar")

    assert Settings(_env_file=None).database_url == "postgresql+psycopg://u:s@host/radar"


def test_engine_do_postgresql_carrega_o_driver_instalado() -> None:
    # create_engine não abre conexão: só confirma que o driver está instalado e é o esperado.
    engine = create_engine(_database_url("postgresql://u:s@host/radar"))

    assert (engine.dialect.name, engine.dialect.driver) == ("postgresql", "psycopg")


@pytest.mark.parametrize("table", Base.metadata.sorted_tables, ids=lambda table: table.name)
def test_sql_das_tabelas_e_valido_para_o_postgresql(table) -> None:
    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect())).strip()

    assert ddl.startswith(f"CREATE TABLE {table.name} (")


def test_postgresql_recebe_o_tamanho_das_colunas_de_texto() -> None:
    # O SQLite ignora o tamanho; o PostgreSQL o impõe (ver limits.py).
    ddl = str(CreateTable(Base.metadata.tables["dispatch_codes"]).compile(dialect=postgresql.dialect()))

    assert "code VARCHAR(10) NOT NULL" in ddl
    assert "official_description VARCHAR(500) NOT NULL" in ddl
