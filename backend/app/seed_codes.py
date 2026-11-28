"""Carga dos códigos de despacho do INPI no glossário (tabela dispatch_codes).

Execute a partir da pasta backend:  python -m app.seed_codes

Pode ser usado em produção: grava só os códigos de despacho, não cria usuários nem ativos e não
tem opção para apagar dados.

- Idempotente pela chave (asset_type, code): código novo é inserido; código existente é atualizado
  se a descrição, a explicação, "exige ação" ou o prazo mudaram na tabela.
- Valida a tabela inteira antes de gravar: qualquer problema recusa a carga toda. Nenhum texto é
  cortado, para não adulterar a descrição oficial.
- Nunca apaga: código do banco que não está na tabela é mantido e só gera aviso (apagá-lo
  desligaria os despachos ligados a ele, por causa do ON DELETE SET NULL).
- Alertas já criados guardam "exige ação" e prazo do momento em que foram criados; só a explicação
  em linguagem simples é lida do glossário na hora.
"""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.database.init_db import init_db
from app.dispatch_codes_data import DISPATCH_CODES, DispatchCodeEntry
from app.models import AssetType, DispatchCode
from app.models.limits import (
    DISPATCH_CODE_MAX_LENGTH,
    DISPATCH_DESCRIPTION_MAX_LENGTH,
    DISPATCH_PLAIN_DESCRIPTION_MAX_LENGTH,
)

Key = tuple[AssetType, str]

AVISO_TABELA_VAZIA = (
    "AVISO: não há códigos de despacho para carregar (a tabela em app/dispatch_codes_data.py está vazia)."
)

# Campos que a carga atualiza num código existente; a chave (asset_type, code) não muda.
_UPDATABLE_FIELDS = ("official_description", "plain_description", "requires_action", "deadline_days")

_TEXT_LIMITS = {
    "official_description": DISPATCH_DESCRIPTION_MAX_LENGTH,
    "plain_description": DISPATCH_PLAIN_DESCRIPTION_MAX_LENGTH,
}


class InvalidDispatchCodesError(ValueError):
    """A tabela de códigos tem problemas; nada foi gravado. `problems` lista todos de uma vez."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Tabela de códigos de despacho inválida:\n" + "\n".join(f"  - {p}" for p in problems))


@dataclass(frozen=True)
class SeedCodesResult:
    """Resumo de uma carga."""

    total: int  # códigos na tabela
    inserted: tuple[Key, ...] = ()
    updated: tuple[Key, ...] = ()
    unchanged: int = 0
    not_in_table: tuple[Key, ...] = ()  # no banco, mas fora da tabela (mantidos)


def _label(index: int, entry: DispatchCodeEntry) -> str:
    asset_type = entry.asset_type.value if isinstance(entry.asset_type, AssetType) else repr(entry.asset_type)
    return f"linha {index + 1} ({asset_type} {entry.code!r})"


def _format_key(key: Key) -> str:
    return f"{key[0].value} {key[1]}"


def validate_entries(entries: Sequence[DispatchCodeEntry]) -> None:
    """Confere a tabela inteira e levanta InvalidDispatchCodesError com todos os problemas encontrados.

    Os limites vêm de models/limits.py: o SQLite não recusa texto maior que a coluna, mas o
    PostgreSQL recusa (e o VARCHAR dele conta caracteres, como o len() do Python).
    """
    problems: list[str] = []
    seen: dict[Key, int] = {}

    for index, entry in enumerate(entries):
        where = _label(index, entry)

        if not isinstance(entry.asset_type, AssetType):
            problems.append(f"{where}: tipo de ativo deve ser um AssetType.")

        code = entry.code
        if not isinstance(code, str) or not code:
            problems.append(f"{where}: código vazio ou que não é texto.")
        else:
            if any(char.isspace() for char in code):
                problems.append(f"{where}: código não pode ter espaços (deve ser igual ao lido da RPI).")
            if len(code) > DISPATCH_CODE_MAX_LENGTH:
                problems.append(f"{where}: código passa de {DISPATCH_CODE_MAX_LENGTH} caracteres.")

        for name, limit in _TEXT_LIMITS.items():
            text = getattr(entry, name)
            if not isinstance(text, str) or not text.strip():
                problems.append(f"{where}: {name} vazio ou que não é texto.")
                continue
            if text != text.strip():
                problems.append(f"{where}: {name} com espaços no início ou no fim.")
            if len(text) > limit:
                problems.append(f"{where}: {name} tem {len(text)} caracteres; o máximo é {limit}.")

        if not isinstance(entry.requires_action, bool):
            problems.append(f"{where}: requires_action deve ser True ou False.")

        days = entry.deadline_days
        if days is not None:
            # bool é subclasse de int: True não pode passar por prazo de 1 dia.
            if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
                problems.append(f"{where}: deadline_days deve ser um número inteiro de dias maior que zero, ou vazio.")
            elif entry.requires_action is not True:
                problems.append(f"{where}: deadline_days só vale para código que exige ação (os alertas ignoram).")

        if isinstance(entry.asset_type, AssetType) and isinstance(code, str):
            key = (entry.asset_type, code)
            if key in seen:
                problems.append(f"{where}: repete o código da linha {seen[key] + 1}.")
            else:
                seen[key] = index

    if problems:
        raise InvalidDispatchCodesError(problems)


def seed_dispatch_codes(db: Session, entries: Sequence[DispatchCodeEntry] | None = None) -> SeedCodesResult:
    """Insere ou atualiza os códigos de despacho pela chave (asset_type, code).

    Sem `entries`, usa DISPATCH_CODES. Valida tudo antes de gravar. Não faz commit: quem chama
    decide quando gravar, para a carga entrar na mesma transação do seed de demonstração.
    """
    if entries is None:
        entries = DISPATCH_CODES
    validate_entries(entries)

    existing: dict[Key, DispatchCode] = {(row.asset_type, row.code): row for row in db.scalars(select(DispatchCode))}

    inserted: list[Key] = []
    updated: list[Key] = []
    unchanged = 0
    for entry in entries:
        key = (entry.asset_type, entry.code)
        values = {name: getattr(entry, name) for name in _UPDATABLE_FIELDS}
        row = existing.get(key)
        if row is None:
            db.add(DispatchCode(asset_type=entry.asset_type, code=entry.code, **values))
            inserted.append(key)
        elif any(getattr(row, name) != value for name, value in values.items()):
            for name, value in values.items():
                setattr(row, name, value)
            updated.append(key)
        else:
            unchanged += 1
    db.flush()

    table_keys = {(entry.asset_type, entry.code) for entry in entries}
    not_in_table = sorted((key for key in existing if key not in table_keys), key=lambda k: (k[0].value, k[1]))

    return SeedCodesResult(
        total=len(entries),
        inserted=tuple(inserted),
        updated=tuple(updated),
        unchanged=unchanged,
        not_in_table=tuple(not_in_table),
    )


def print_summary(result: SeedCodesResult) -> None:
    """Mostra no terminal o que a carga fez.

    Os códigos novos só entram na contagem (são centenas na primeira carga); os atualizados e os que
    estão fora da tabela são listados um a um, porque são poucos e merecem conferência.
    """
    if result.total == 0:
        print(f"  {AVISO_TABELA_VAZIA}")
    for key in result.updated:
        print(f"  ~ código {_format_key(key)} atualizado")
    for key in result.not_in_table:
        print(f"  ! código {_format_key(key)} está no banco, mas não na tabela (mantido)")
    if result.total:
        print(
            f"  Códigos de despacho: {len(result.inserted)} novos, {len(result.updated)} atualizados, "
            f"{result.unchanged} sem mudança."
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Carrega os códigos de despacho do INPI no glossário. Não cria usuários nem ativos."
    )
    parser.parse_args(argv)  # sem --reset de propósito: este comando também roda em produção

    if not DISPATCH_CODES:
        print(AVISO_TABELA_VAZIA)
        return

    try:
        validate_entries(DISPATCH_CODES)
    except InvalidDispatchCodesError as exc:
        print(exc)
        raise SystemExit(1) from None

    init_db()
    print("Carregando os códigos de despacho...")
    with SessionLocal() as db:
        result = seed_dispatch_codes(db, DISPATCH_CODES)
        db.commit()
    print_summary(result)
    print("Pronto.")


if __name__ == "__main__":
    main()
