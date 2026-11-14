"""Tipos de coluna reutilizados pelos models."""

from enum import Enum

from sqlalchemy import Enum as SAEnum


def enum_column_type(enum_class: type[Enum], *, name: str, length: int) -> SAEnum:
    """Coluna de enum gravada como texto com CHECK constraint, igual no SQLite e no PostgreSQL.

    - native_enum=False: não cria um tipo ENUM no banco; grava VARCHAR(length) + CHECK.
    - values_callable: grava o VALOR do membro ("Programa de Computador"), não o NOME
      ("PROGRAMA_DE_COMPUTADOR"). Sem isso, a API continuaria funcionando, mas os bancos já
      existentes deixariam de ser lidos (ver tests/test_esquema_banco.py).
    """
    return SAEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda enum: [member.value for member in enum],
        length=length,
    )
