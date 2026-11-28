"""Tabela oficial de códigos de despacho (app/dispatch_codes_data.py), conferida contra as fixtures da RPI.

Os testes da carga com dados fictícios ficam em test_seed_codes.py.
"""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dispatch_codes_data import DISPATCH_CODES, FONTE, DispatchCodeEntry
from app.models import Asset, AssetType, Dispatch, DispatchCode, RpiEdition, User
from app.seed_codes import seed_dispatch_codes, validate_entries
from app.services.alert_service import create_alerts_for
from app.services.rpi_parser import ParsedDispatch, parse_edition

PATENTE = AssetType.PATENTE
PROGRAMA = AssetType.PROGRAMA_DE_COMPUTADOR

FIXTURES = Path(__file__).parent / "fixtures" / "rpi"
EDICAO_2916 = {PATENTE: FIXTURES / "patentes_2916.xml", PROGRAMA: FIXTURES / "programas_2916.xml"}


def _tabela() -> dict[tuple[AssetType, str], DispatchCodeEntry]:
    return {(entry.asset_type, entry.code): entry for entry in DISPATCH_CODES}


def _despachos_das_fixtures() -> tuple[ParsedDispatch, ...]:
    return parse_edition(EDICAO_2916, 2916).dispatches


def test_tabela_oficial_passa_na_validacao() -> None:
    validate_entries(DISPATCH_CODES)


def test_tabela_tem_codigos_de_patentes_e_de_programas() -> None:
    tipos = {entry.asset_type for entry in DISPATCH_CODES}

    assert tipos == {PATENTE, PROGRAMA}


def test_todos_os_codigos_das_fixtures_estao_na_tabela() -> None:
    # Usa o próprio parser: o código precisa estar na tabela exatamente como a RPI o entrega.
    faltando = {(d.asset_type, d.code) for d in _despachos_das_fixtures()} - set(_tabela())

    assert faltando == set()


def test_descricao_oficial_e_o_titulo_publicado_na_rpi() -> None:
    tabela = _tabela()

    for despacho in _despachos_das_fixtures():
        assert tabela[(despacho.asset_type, despacho.code)].official_description == despacho.description


@pytest.mark.parametrize("asset_type", list(AssetType))
def test_fonte_de_cada_tipo_tem_titulo_e_data_de_consulta(asset_type: AssetType) -> None:
    fonte = FONTE[asset_type]

    assert fonte.titulo
    assert isinstance(fonte.data_consulta, date)


@pytest.mark.parametrize(
    ("asset_type", "code", "requires_action", "deadline_days"),
    [
        (PATENTE, "6.1", True, 90),  # exigência técnica: 90 dias corridos da publicação
        (PATENTE, "2.5", True, 30),  # exigência formal preliminar: 30 dias corridos
        (PATENTE, "9.2", True, 60),  # indeferimento: recurso em 60 dias
        (PATENTE, "7.1", True, 90),  # ciência de parecer: 90 dias corridos
        (PATENTE, "8.6", True, None),  # restauração em 3 meses: prazo em meses não vira número
        (PATENTE, "6.10", True, None),  # republicação: 90 ou 60 dias, conforme a exigência original
        (PATENTE, "141", True, None),  # tabela contraditória: "60 (noventa) dias"
        (PATENTE, "16.1", False, None),  # concessão: os 6 meses são para terceiros
        (PATENTE, "15.11", False, None),  # alteração de classificação (fixture)
        (PROGRAMA, "092", True, 60),  # alteração de nome em exigência
        (PROGRAMA, "115", True, 30),  # recurso de terceiro contra o deferimento: contrarrazões em 30 dias
        (PROGRAMA, "082", True, None),  # prazo contado da notificação, não "desta data"
        (PROGRAMA, "730", False, None),  # certificado expedido (fixture)
    ],
)
def test_exige_acao_e_prazo_conferidos_na_tabela_oficial(
    asset_type: AssetType, code: str, requires_action: bool, deadline_days: int | None
) -> None:
    entry = _tabela()[(asset_type, code)]

    assert (entry.requires_action, entry.deadline_days) == (requires_action, deadline_days)


def test_mesmo_codigo_tem_sentidos_diferentes_em_patentes_e_programas() -> None:
    tabela = _tabela()

    assert tabela[(PATENTE, "111")].official_description != tabela[(PROGRAMA, "111")].official_description


def test_codigo_da_tabela_carregada_gera_alerta_com_prazo(
    db_session: Session, users: dict[str, User], assets: list[Asset]
) -> None:
    seed_dispatch_codes(db_session)
    db_session.commit()
    exigencia = db_session.scalar(
        select(DispatchCode).where(DispatchCode.asset_type == PATENTE, DispatchCode.code == "6.1")
    )
    edicao = RpiEdition(number=2916, publication_date=date(2026, 11, 24))
    despacho = Dispatch(
        edition=edicao,
        asset=assets[0],
        process_number=assets[0].process_number,
        code="6.1",
        dispatch_code=exigencia,
        description="Exigência Técnica - Art. 36 da LPI",
        publication_date=edicao.publication_date,
    )
    db_session.add(despacho)

    alertas = create_alerts_for(db_session, despacho)

    assert alertas
    assert {(a.requires_action, a.deadline) for a in alertas} == {(True, date(2027, 2, 22))}
    assert all(a.dispatch_plain_description == exigencia.plain_description for a in alertas)
