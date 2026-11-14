"""Testes de caracterização do esquema (Sprint 3, Parte 2).

Escritos ANTES das refatorações DT-01 (limites de tamanho) e DT-02 (configuração dos enums) para capturar o
comportamento atual de algo que a suíte da API não enxerga: o formato do banco. Se os enums passassem a gravar o
NOME do membro ("PROGRAMA_DE_COMPUTADOR") em vez do valor, a API continuaria respondendo igual, mas os bancos já
existentes (pi_inpi.db) deixariam de ser lidos.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.main import create_app
from app.models import Asset, AssetType, User, UserRole

DDL_USERS = """CREATE TABLE users (
\tid INTEGER NOT NULL,
\temail VARCHAR(255) NOT NULL,
\thashed_password VARCHAR(255) NOT NULL,
\trole VARCHAR(20) NOT NULL,
\tPRIMARY KEY (id),
\tCONSTRAINT user_role CHECK (role IN ('NIT', 'AUTOR'))
)"""

DDL_ASSETS = """CREATE TABLE assets (
\tid INTEGER NOT NULL,
\ttitle VARCHAR(500) NOT NULL,
\tasset_type VARCHAR(40) NOT NULL,
\tprocess_number VARCHAR(50) NOT NULL,
\tdeposit_date DATE NOT NULL,
\tstatus VARCHAR(100) NOT NULL,
\tauthors VARCHAR(1000) NOT NULL,
\tauthor_user_id INTEGER,
\tPRIMARY KEY (id),
\tCONSTRAINT asset_type CHECK (asset_type IN ('Patente', 'Programa de Computador')),
\tFOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE SET NULL
)"""


def _linhas(ddl: str) -> list[str]:
    return [linha.strip() for linha in ddl.strip().splitlines()]


def _ddl(table) -> list[str]:
    return _linhas(str(CreateTable(table).compile(dialect=sqlite.dialect())))


def test_ddl_da_tabela_users_nao_muda() -> None:
    assert _ddl(User.__table__) == _linhas(DDL_USERS)


def test_ddl_da_tabela_assets_nao_muda() -> None:
    assert _ddl(Asset.__table__) == _linhas(DDL_ASSETS)


def test_indices_unicos_continuam_os_mesmos() -> None:
    indices = {(index.name, index.unique) for table in (User.__table__, Asset.__table__) for index in table.indexes}

    assert indices == {
        ("ix_users_email", True),
        ("ix_assets_process_number", True),
        ("ix_assets_author_user_id", False),
    }


def test_enums_gravam_o_valor_e_nao_o_nome(db_session: Session, users) -> None:
    db_session.add(
        Asset(
            title="Software qualquer",
            asset_type=AssetType.PROGRAMA_DE_COMPUTADOR,
            process_number="BR 51 2025 000123-4",
            deposit_date=date(2025, 1, 2),
            status="Registrado",
            authors="Alguém",
        )
    )
    db_session.commit()

    tipo = db_session.execute(text("SELECT asset_type FROM assets")).scalar_one()
    perfis = set(db_session.execute(text("SELECT role FROM users")).scalars())
    assert tipo == "Programa de Computador"
    assert perfis == {UserRole.NIT.value, UserRole.AUTOR.value}


def test_check_constraint_recusa_perfil_fora_do_enum(db_session: Session) -> None:
    try:
        db_session.execute(text("INSERT INTO users (email, hashed_password, role) VALUES ('x@x.br', 'h', 'ADMIN')"))
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:  # pragma: no cover - só executa se a restrição sumir
        raise AssertionError("o CHECK do perfil deixou de existir")


def test_limites_publicados_no_openapi_do_cadastro() -> None:
    schema = create_app().openapi()["components"]["schemas"]["AssetCreate"]["properties"]

    limites = {campo: (schema[campo].get("minLength"), schema[campo].get("maxLength")) for campo in schema}
    assert limites["title"] == (3, 500)
    assert limites["process_number"] == (5, 50)
    assert limites["status"] == (2, 100)
    assert limites["authors"] == (2, 1000)
