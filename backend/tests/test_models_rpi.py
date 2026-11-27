"""Testes dos models da RPI: RpiEdition, DispatchCode e Dispatch (base das US08, US09 e US10)."""

from datetime import date

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Asset, AssetType, Dispatch, DispatchCode, RpiEdition, RpiEditionStatus


@pytest.fixture
def edition(db_session: Session) -> RpiEdition:
    created = RpiEdition(number=2862, publication_date=date(2026, 11, 24))
    db_session.add(created)
    db_session.commit()
    return created


@pytest.fixture
def dispatch_code(db_session: Session) -> DispatchCode:
    created = DispatchCode(
        code="6.1",
        asset_type=AssetType.PATENTE,
        official_description="Exigência técnica",
        plain_description="O INPI pediu ajustes no pedido. É preciso responder dentro do prazo.",
        requires_action=True,
        deadline_days=90,
    )
    db_session.add(created)
    db_session.commit()
    return created


def _dispatch(edition: RpiEdition, asset: Asset, code: str = "6.1", **extra) -> Dispatch:
    return Dispatch(
        edition=edition,
        asset=asset,
        process_number=asset.process_number,
        code=code,
        description="Exigência técnica",
        publication_date=edition.publication_date,
        **extra,
    )


def _total_dispatches(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(Dispatch))


# --- Criação ---------------------------------------------------------------------------------------------------------


def test_cria_edicao_com_valores_padrao(db_session: Session, edition: RpiEdition) -> None:
    db_session.refresh(edition)

    assert edition.status == RpiEditionStatus.BAIXADA
    assert edition.dispatch_count == 0
    assert edition.file_path is None
    assert edition.error_message is None
    assert edition.processed_at is None


def test_cria_codigo_de_despacho_sem_prazo(db_session: Session) -> None:
    code = DispatchCode(
        code="730",
        asset_type=AssetType.PROGRAMA_DE_COMPUTADOR,
        official_description="Registro concedido",
        plain_description="O programa foi registrado.",
    )
    db_session.add(code)
    db_session.commit()
    db_session.refresh(code)

    assert code.requires_action is False
    assert code.deadline_days is None


def test_cria_despacho_ligado_a_edicao_ativo_e_codigo(
    db_session: Session, edition: RpiEdition, assets: list[Asset], dispatch_code: DispatchCode
) -> None:
    dispatch = _dispatch(edition, assets[0], dispatch_code=dispatch_code, complement="Prazo de 90 dias.")
    db_session.add(dispatch)
    db_session.commit()
    db_session.expire_all()

    salvo = db_session.get(Dispatch, dispatch.id)
    assert salvo.edition.number == 2862
    assert salvo.asset.process_number == "BR 10 2023 000001-1"
    assert salvo.dispatch_code.requires_action is True
    assert salvo.complement == "Prazo de 90 dias."
    assert db_session.get(RpiEdition, edition.id).dispatches == [salvo]


def test_despacho_aceita_codigo_fora_do_glossario(
    db_session: Session, edition: RpiEdition, assets: list[Asset]
) -> None:
    db_session.add(_dispatch(edition, assets[0], code="99.9"))
    db_session.commit()

    assert db_session.scalar(select(Dispatch.dispatch_code_id)) is None


def test_despacho_exige_ativo(db_session: Session, edition: RpiEdition) -> None:
    db_session.add(
        Dispatch(
            edition=edition,
            process_number="BR 10 2023 999999-9",
            code="6.1",
            description="Sem ativo",
            publication_date=edition.publication_date,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


# --- Unicidade -------------------------------------------------------------------------------------------------------


def test_numero_da_edicao_e_unico(db_session: Session, edition: RpiEdition) -> None:
    db_session.add(RpiEdition(number=2862, publication_date=date(2026, 12, 1)))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_codigo_e_unico_por_tipo_de_ativo(db_session: Session, dispatch_code: DispatchCode) -> None:
    # Mesmo código na seção de programas: permitido.
    db_session.add(
        DispatchCode(
            code="6.1",
            asset_type=AssetType.PROGRAMA_DE_COMPUTADOR,
            official_description="Outro sentido",
            plain_description="Outro sentido.",
        )
    )
    db_session.commit()

    # Mesmo código na mesma seção: recusado.
    db_session.add(
        DispatchCode(
            code="6.1",
            asset_type=AssetType.PATENTE,
            official_description="Duplicado",
            plain_description="Duplicado.",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_reprocessar_edicao_nao_duplica_despacho(
    db_session: Session, edition: RpiEdition, assets: list[Asset]
) -> None:
    db_session.add(_dispatch(edition, assets[0]))
    db_session.commit()

    db_session.add(_dispatch(edition, assets[0]))
    with pytest.raises(IntegrityError):
        db_session.commit()


# --- Cascata ---------------------------------------------------------------------------------------------------------


def test_apagar_edicao_apaga_os_despachos(db_session: Session, edition: RpiEdition, assets: list[Asset]) -> None:
    db_session.add_all([_dispatch(edition, assets[0]), _dispatch(edition, assets[1])])
    db_session.commit()

    db_session.delete(edition)
    db_session.commit()

    assert _total_dispatches(db_session) == 0


def test_apagar_ativo_apaga_os_despachos(db_session: Session, edition: RpiEdition, assets: list[Asset]) -> None:
    db_session.add_all([_dispatch(edition, assets[0]), _dispatch(edition, assets[1])])
    db_session.commit()

    db_session.delete(assets[0])
    db_session.commit()
    db_session.expire_all()

    restantes = db_session.scalars(select(Dispatch)).all()
    assert [d.asset_id for d in restantes] == [assets[1].id]


def test_apagar_codigo_mantem_o_despacho(
    db_session: Session, edition: RpiEdition, assets: list[Asset], dispatch_code: DispatchCode
) -> None:
    db_session.add(_dispatch(edition, assets[0], dispatch_code=dispatch_code))
    db_session.commit()

    db_session.delete(dispatch_code)
    db_session.commit()
    db_session.expire_all()

    assert _total_dispatches(db_session) == 1
    assert db_session.scalar(select(Dispatch.dispatch_code_id)) is None


# --- Enum gravando o valor -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", list(RpiEditionStatus))
def test_status_da_edicao_grava_o_valor(db_session: Session, status: RpiEditionStatus) -> None:
    db_session.add(RpiEdition(number=3000, publication_date=date(2026, 12, 1), status=status))
    db_session.commit()

    assert db_session.execute(text("SELECT status FROM rpi_editions")).scalar_one() == status.value


def test_tipo_do_codigo_grava_o_valor(db_session: Session, dispatch_code: DispatchCode) -> None:
    assert db_session.execute(text("SELECT asset_type FROM dispatch_codes")).scalar_one() == "Patente"


def test_check_constraint_recusa_status_fora_do_enum(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("INSERT INTO rpi_editions (number, publication_date, status, dispatch_count) "
                 "VALUES (1, '2026-01-01', 'PROCESSADA', 0)")
        )
