"""Testes contra um PostgreSQL de verdade. Só rodam com a variável TEST_POSTGRES_URL definida.

ATENÇÃO: as tabelas do banco indicado são APAGADAS e recriadas. Use um banco descartável, por exemplo:

    docker run --rm -d --name radar-pg -e POSTGRES_PASSWORD=teste -p 5433:5432 postgres:17
    set TEST_POSTGRES_URL=postgresql://postgres:teste@localhost:5433/postgres   (macOS/Linux: export)
    pytest tests/test_postgresql.py
"""

import os
from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.core.config import Settings
from app.database import Base
from app.models import Asset, AssetType, Dispatch, DispatchCode, RpiEdition, User
from app.models.limits import DISPATCH_CODE_MAX_LENGTH
from app.seed import DEMO_ASSETS, DEMO_USERS, seed

TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "")

pytestmark = pytest.mark.skipif(not TEST_POSTGRES_URL, reason="defina TEST_POSTGRES_URL para testar no PostgreSQL")


@pytest.fixture
def pg_session() -> Iterator[Session]:
    engine = create_engine(Settings(database_url=TEST_POSTGRES_URL, _env_file=None).database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _code(code: str) -> DispatchCode:
    return DispatchCode(
        code=code,
        asset_type=AssetType.PATENTE,
        official_description="Descrição fictícia",
        plain_description="Explicação fictícia.",
    )


def test_cria_todas_as_tabelas(pg_session: Session) -> None:
    criadas = set(inspect(pg_session.get_bind()).get_table_names())

    assert set(Base.metadata.tables) <= criadas


def test_seed_de_demonstracao_funciona(pg_session: Session) -> None:
    seed(pg_session)
    seed(pg_session)

    assert pg_session.scalar(select(func.count(User.id))) == len(DEMO_USERS)
    assert pg_session.scalar(select(func.count(Asset.id))) == len(DEMO_ASSETS)


def test_enum_grava_o_valor_e_check_recusa_o_nome(pg_session: Session) -> None:
    seed(pg_session)

    tipos = set(pg_session.scalars(text("SELECT asset_type FROM assets")))
    assert tipos == {"Patente", "Programa de Computador"}

    with pytest.raises(IntegrityError):
        pg_session.execute(text("UPDATE assets SET asset_type = 'PATENTE'"))
    pg_session.rollback()


def test_recusa_texto_maior_que_a_coluna(pg_session: Session) -> None:
    # Diferente do SQLite: é por isso que os limites de limits.py são validados antes de gravar.
    pg_session.add(_code("X" * (DISPATCH_CODE_MAX_LENGTH + 1)))

    with pytest.raises(DataError):
        pg_session.commit()
    pg_session.rollback()


def test_apagar_edicao_apaga_despachos_e_apagar_codigo_desliga(pg_session: Session) -> None:
    seed(pg_session)
    asset = pg_session.scalars(select(Asset)).first()
    code = _code("T.1")  # fictício: o seed já carrega os códigos oficiais, como o 6.1
    edition = RpiEdition(number=2916, publication_date=date(2026, 11, 24))
    pg_session.add(
        Dispatch(
            edition=edition,
            asset=asset,
            process_number=asset.process_number,
            code="T.1",
            dispatch_code=code,
            description="Despacho fictício",
            publication_date=edition.publication_date,
        )
    )
    pg_session.commit()

    pg_session.delete(code)
    pg_session.commit()
    assert pg_session.scalar(select(Dispatch.dispatch_code_id)) is None  # ON DELETE SET NULL

    pg_session.delete(edition)
    pg_session.commit()
    assert pg_session.scalar(select(func.count(Dispatch.id))) == 0  # ON DELETE CASCADE
