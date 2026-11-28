"""Validação e carga dos códigos de despacho no glossário (app/seed_codes.py).

Usa só códigos fictícios ("T.1", "T.2"...), definidos aqui: os testes não dependem da tabela oficial.
"""

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import seed_codes
from app.dispatch_codes_data import DispatchCodeEntry
from app.models import Asset, AssetType, Dispatch, DispatchCode, RpiEdition, User
from app.models.limits import (
    DISPATCH_CODE_MAX_LENGTH,
    DISPATCH_DESCRIPTION_MAX_LENGTH,
    DISPATCH_PLAIN_DESCRIPTION_MAX_LENGTH,
)
from app.seed_codes import InvalidDispatchCodesError, seed_dispatch_codes, validate_entries

PATENTE = AssetType.PATENTE
PROGRAMA = AssetType.PROGRAMA_DE_COMPUTADOR


def _entry(**overrides) -> DispatchCodeEntry:
    base = DispatchCodeEntry(
        asset_type=PATENTE,
        code="T.1",
        official_description="Descrição oficial fictícia T.1",
        plain_description="Explicação fictícia T.1.",
    )
    return replace(base, **overrides)


FICTICIOS = (
    _entry(),
    _entry(
        code="T.2",
        official_description="Descrição oficial fictícia T.2",
        plain_description="Explicação fictícia T.2.",
        requires_action=True,
        deadline_days=30,
    ),
    _entry(asset_type=PROGRAMA, code="T.1", official_description="Outro sentido T.1", requires_action=True),
)


def _problems(*entries: DispatchCodeEntry) -> list[str]:
    with pytest.raises(InvalidDispatchCodesError) as exc_info:
        validate_entries(entries)
    return exc_info.value.problems


def _count(db_session: Session, model: type) -> int:
    return db_session.scalar(select(func.count()).select_from(model))


def _codes_in_db(db_session: Session) -> dict[tuple[AssetType, str], DispatchCode]:
    return {(row.asset_type, row.code): row for row in db_session.scalars(select(DispatchCode))}


# --- validate_entries: casos aceitos ---------------------------------------------------------------------------------


def test_tabela_valida_passa() -> None:
    validate_entries(FICTICIOS)


def test_tabela_vazia_e_valida() -> None:
    validate_entries(())


def test_mesmo_codigo_em_tipos_diferentes_e_permitido() -> None:
    validate_entries([_entry(asset_type=PATENTE), _entry(asset_type=PROGRAMA)])


def test_aceita_textos_no_limite_exato_das_colunas() -> None:
    validate_entries(
        [
            _entry(
                code="T" * DISPATCH_CODE_MAX_LENGTH,
                official_description="á" * DISPATCH_DESCRIPTION_MAX_LENGTH,  # acento conta como 1 caractere
                plain_description="é" * DISPATCH_PLAIN_DESCRIPTION_MAX_LENGTH,
            )
        ]
    )


def test_aceita_codigo_que_exige_acao_sem_prazo() -> None:
    validate_entries([_entry(requires_action=True, deadline_days=None)])


# --- validate_entries: tipo de ativo e código ------------------------------------------------------------------------


def test_recusa_tipo_de_ativo_que_nao_e_asset_type() -> None:
    assert any("tipo de ativo" in p for p in _problems(_entry(asset_type="Patente")))


@pytest.mark.parametrize("code", ["", None, 6.1])
def test_recusa_codigo_vazio_ou_que_nao_e_texto(code: object) -> None:
    assert any("código vazio" in p for p in _problems(_entry(code=code)))


@pytest.mark.parametrize("code", ["T 1", " T.1", "T.1 ", "T.1\t", "T.\n1"])
def test_recusa_codigo_com_espacos(code: str) -> None:
    assert any("espaços" in p for p in _problems(_entry(code=code)))


def test_recusa_codigo_maior_que_a_coluna() -> None:
    problems = _problems(_entry(code="T" * (DISPATCH_CODE_MAX_LENGTH + 1)))
    assert any(f"{DISPATCH_CODE_MAX_LENGTH} caracteres" in p for p in problems)


# --- validate_entries: textos ----------------------------------------------------------------------------------------

TEXT_FIELDS = [
    ("official_description", DISPATCH_DESCRIPTION_MAX_LENGTH),
    ("plain_description", DISPATCH_PLAIN_DESCRIPTION_MAX_LENGTH),
]


@pytest.mark.parametrize(("field", "_limit"), TEXT_FIELDS)
@pytest.mark.parametrize("value", ["", "   ", None, 123])
def test_recusa_texto_vazio_ou_que_nao_e_texto(field: str, _limit: int, value: object) -> None:
    assert any(f"{field} vazio" in p for p in _problems(_entry(**{field: value})))


@pytest.mark.parametrize(("field", "_limit"), TEXT_FIELDS)
@pytest.mark.parametrize("value", [" Texto fictício", "Texto fictício ", "Texto fictício\n"])
def test_recusa_texto_com_espacos_nas_pontas(field: str, _limit: int, value: str) -> None:
    assert any(f"{field} com espaços" in p for p in _problems(_entry(**{field: value})))


@pytest.mark.parametrize(("field", "limit"), TEXT_FIELDS)
def test_recusa_texto_maior_que_a_coluna_sem_cortar(field: str, limit: int) -> None:
    problems = _problems(_entry(**{field: "x" * (limit + 1)}))
    assert any(f"{field} tem {limit + 1} caracteres; o máximo é {limit}" in p for p in problems)


# --- validate_entries: exige ação e prazo ----------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["sim", 1, 0, None])
def test_recusa_requires_action_que_nao_e_booleano(value: object) -> None:
    assert any("requires_action" in p for p in _problems(_entry(requires_action=value)))


@pytest.mark.parametrize("days", [0, -5, "90", 1.5, True])
def test_recusa_prazo_que_nao_e_inteiro_positivo(days: object) -> None:
    assert any("maior que zero" in p for p in _problems(_entry(requires_action=True, deadline_days=days)))


def test_aceita_prazo_inteiro_positivo_em_codigo_que_exige_acao() -> None:
    validate_entries([_entry(requires_action=True, deadline_days=1)])


def test_recusa_prazo_em_codigo_que_nao_exige_acao() -> None:
    problems = _problems(_entry(requires_action=False, deadline_days=30))
    assert any("só vale para código que exige ação" in p for p in problems)


# --- validate_entries: chave e mensagens -----------------------------------------------------------------------------


def test_recusa_chave_repetida_no_mesmo_tipo() -> None:
    problems = _problems(_entry(), _entry(official_description="Duplicada"))
    assert problems == ["linha 2 (Patente 'T.1'): repete o código da linha 1."]


def test_lista_todos_os_problemas_de_uma_vez() -> None:
    problems = _problems(_entry(code=""), _entry(code="T.2", plain_description=" x"), _entry(code="T.3"))

    assert len(problems) == 2
    assert problems[0].startswith("linha 1 ")
    assert problems[1].startswith("linha 2 (Patente 'T.2')")


# --- seed_dispatch_codes ---------------------------------------------------------------------------------------------


def test_carga_insere_os_codigos(db_session: Session) -> None:
    result = seed_dispatch_codes(db_session, FICTICIOS)
    db_session.commit()

    gravados = _codes_in_db(db_session)
    assert set(gravados) == {(PATENTE, "T.1"), (PATENTE, "T.2"), (PROGRAMA, "T.1")}
    t2 = gravados[(PATENTE, "T.2")]
    assert t2.official_description == "Descrição oficial fictícia T.2"
    assert t2.plain_description == "Explicação fictícia T.2."
    assert (t2.requires_action, t2.deadline_days) == (True, 30)
    assert gravados[(PROGRAMA, "T.1")].official_description == "Outro sentido T.1"
    assert result.total == 3
    assert result.inserted == ((PATENTE, "T.1"), (PATENTE, "T.2"), (PROGRAMA, "T.1"))
    assert (result.updated, result.unchanged, result.not_in_table) == ((), 0, ())


def test_carga_e_idempotente(db_session: Session) -> None:
    seed_dispatch_codes(db_session, FICTICIOS)
    db_session.commit()

    segunda = seed_dispatch_codes(db_session, FICTICIOS)
    db_session.commit()

    assert _count(db_session, DispatchCode) == len(FICTICIOS)
    assert (segunda.inserted, segunda.updated, segunda.unchanged) == ((), (), len(FICTICIOS))


def test_carga_atualiza_descricao_e_prazo_corrigidos(db_session: Session) -> None:
    seed_dispatch_codes(db_session, FICTICIOS)
    db_session.commit()
    id_antes = _codes_in_db(db_session)[(PATENTE, "T.2")].id

    corrigido = replace(
        FICTICIOS[1],
        official_description="Descrição corrigida",
        plain_description="Explicação corrigida.",
        deadline_days=60,
    )
    result = seed_dispatch_codes(db_session, [FICTICIOS[0], corrigido, FICTICIOS[2]])
    db_session.commit()
    db_session.expire_all()

    t2 = _codes_in_db(db_session)[(PATENTE, "T.2")]
    assert t2.id == id_antes
    assert (t2.official_description, t2.plain_description, t2.deadline_days) == (
        "Descrição corrigida",
        "Explicação corrigida.",
        60,
    )
    assert (result.inserted, result.updated, result.unchanged) == ((), ((PATENTE, "T.2"),), 2)


def test_carga_atualiza_exige_acao(db_session: Session) -> None:
    seed_dispatch_codes(db_session, [_entry(requires_action=True, deadline_days=30)])
    db_session.commit()

    result = seed_dispatch_codes(db_session, [_entry(requires_action=False, deadline_days=None)])
    db_session.commit()

    t1 = _codes_in_db(db_session)[(PATENTE, "T.1")]
    assert (t1.requires_action, t1.deadline_days) == (False, None)
    assert result.updated == ((PATENTE, "T.1"),)


def test_carga_preserva_o_vinculo_dos_despachos(db_session: Session, assets: list[Asset]) -> None:
    seed_dispatch_codes(db_session, FICTICIOS)
    db_session.commit()
    code = _codes_in_db(db_session)[(PATENTE, "T.1")]
    edition = RpiEdition(number=9999, publication_date=date(2026, 11, 24))
    dispatch = Dispatch(
        edition=edition,
        asset=assets[0],
        process_number=assets[0].process_number,
        code="T.1",
        dispatch_code=code,
        description="Despacho fictício",
        publication_date=edition.publication_date,
    )
    db_session.add(dispatch)
    db_session.commit()

    seed_dispatch_codes(db_session, [replace(FICTICIOS[0], plain_description="Nova explicação."), *FICTICIOS[1:]])
    db_session.commit()
    db_session.expire_all()

    salvo = db_session.get(Dispatch, dispatch.id)
    assert salvo.dispatch_code_id == code.id
    assert salvo.dispatch_code.plain_description == "Nova explicação."


def test_carga_nao_apaga_codigo_fora_da_tabela(db_session: Session) -> None:
    db_session.add(
        DispatchCode(
            code="T.9",
            asset_type=PROGRAMA,
            official_description="Código fictício antigo",
            plain_description="Explicação fictícia antiga.",
        )
    )
    db_session.commit()

    result = seed_dispatch_codes(db_session, FICTICIOS)
    db_session.commit()

    assert (PROGRAMA, "T.9") in _codes_in_db(db_session)
    assert result.not_in_table == ((PROGRAMA, "T.9"),)


def test_carga_nao_cria_usuarios_nem_ativos(db_session: Session) -> None:
    seed_dispatch_codes(db_session, FICTICIOS)
    db_session.commit()

    assert _count(db_session, User) == 0
    assert _count(db_session, Asset) == 0


def test_carga_recusa_tabela_invalida_sem_gravar_nada(db_session: Session) -> None:
    with pytest.raises(InvalidDispatchCodesError):
        seed_dispatch_codes(db_session, [FICTICIOS[0], _entry(code="T.2", deadline_days=10)])

    assert not db_session.new
    db_session.commit()
    assert _count(db_session, DispatchCode) == 0


def test_carga_recusa_tabela_invalida_sem_alterar_codigo_existente(db_session: Session) -> None:
    seed_dispatch_codes(db_session, FICTICIOS)
    db_session.commit()

    with pytest.raises(InvalidDispatchCodesError):
        seed_dispatch_codes(db_session, [replace(FICTICIOS[0], plain_description="Mudou."), _entry(code="")])
    db_session.commit()
    db_session.expire_all()

    assert _codes_in_db(db_session)[(PATENTE, "T.1")].plain_description == "Explicação fictícia T.1."


def test_carga_nao_faz_commit(db_session: Session) -> None:
    seed_dispatch_codes(db_session, FICTICIOS)
    db_session.rollback()

    assert _count(db_session, DispatchCode) == 0


def test_carga_com_tabela_vazia_nao_grava_nada(db_session: Session) -> None:
    result = seed_dispatch_codes(db_session, ())
    db_session.commit()

    assert _count(db_session, DispatchCode) == 0
    assert result == seed_codes.SeedCodesResult(total=0)


def test_carga_sem_entradas_usa_a_tabela_do_modulo(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed_codes, "DISPATCH_CODES", FICTICIOS)

    result = seed_dispatch_codes(db_session)

    assert result.total == len(FICTICIOS)


# --- print_summary ---------------------------------------------------------------------------------------------------


def test_resumo_avisa_tabela_vazia(capsys: pytest.CaptureFixture[str]) -> None:
    seed_codes.print_summary(seed_codes.SeedCodesResult(total=0))

    assert seed_codes.AVISO_TABELA_VAZIA in capsys.readouterr().out


def test_resumo_mostra_inseridos_atualizados_e_fora_da_tabela(capsys: pytest.CaptureFixture[str]) -> None:
    seed_codes.print_summary(
        seed_codes.SeedCodesResult(
            total=2,
            inserted=((PATENTE, "T.1"),),
            updated=((PROGRAMA, "T.1"),),
            not_in_table=((PATENTE, "T.9"),),
        )
    )

    out = capsys.readouterr().out
    assert "+ código Patente T.1" in out
    assert "~ código Programa de Computador T.1 atualizado" in out
    assert "! código Patente T.9 está no banco, mas não na tabela (mantido)" in out
    assert "1 novos, 1 atualizados, 0 sem mudança" in out
    assert seed_codes.AVISO_TABELA_VAZIA not in out


# --- Comando python -m app.seed_codes --------------------------------------------------------------------------------


@pytest.fixture
def comando(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """Faz o main() usar o banco em memória do teste, nunca o banco real."""
    monkeypatch.setattr(seed_codes, "init_db", lambda: None)
    monkeypatch.setattr(seed_codes, "SessionLocal", lambda: db_session)
    return db_session


def test_comando_avisa_tabela_vazia_sem_tocar_no_banco(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _proibido(*_args: object) -> None:
        raise AssertionError("com a tabela vazia, o comando não deve abrir o banco")

    monkeypatch.setattr(seed_codes, "DISPATCH_CODES", ())
    monkeypatch.setattr(seed_codes, "init_db", _proibido)
    monkeypatch.setattr(seed_codes, "SessionLocal", _proibido)

    seed_codes.main([])

    assert seed_codes.AVISO_TABELA_VAZIA in capsys.readouterr().out


def test_comando_carrega_so_os_codigos(
    comando: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(seed_codes, "DISPATCH_CODES", FICTICIOS)

    seed_codes.main([])

    assert _count(comando, DispatchCode) == len(FICTICIOS)
    assert _count(comando, User) == 0
    assert _count(comando, Asset) == 0
    out = capsys.readouterr().out
    assert "3 novos, 0 atualizados, 0 sem mudança" in out
    assert "senha" not in out.lower()


def test_comando_recusa_tabela_invalida_sem_gravar(
    comando: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(seed_codes, "DISPATCH_CODES", (FICTICIOS[0], _entry(code="T 2")))

    with pytest.raises(SystemExit) as exc_info:
        seed_codes.main([])

    assert exc_info.value.code == 1
    assert "linha 2 (Patente 'T 2')" in capsys.readouterr().out
    assert _count(comando, DispatchCode) == 0


def test_comando_nao_tem_opcao_reset() -> None:
    with pytest.raises(SystemExit) as exc_info:
        seed_codes.main(["--reset"])

    assert exc_info.value.code == 2  # argparse: opção desconhecida
