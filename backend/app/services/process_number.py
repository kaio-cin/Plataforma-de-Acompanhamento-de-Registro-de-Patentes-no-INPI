"""Número do processo no INPI: normalização usada para cruzar a RPI com os ativos cadastrados (US09).

A RPI publica "BR 10 2023 001234-5", mas o cadastro pode ter "BR10.2023.001234-5". Os dois lados
são comparados pela forma normalizada, sem alterar o que está gravado.
"""

import re

# Espaços, pontos e hífens não fazem parte da identidade do processo.
_IGNORED_CHARACTERS = re.compile(r"[\s.\-]")

# Formatos vistos na RPI 2916, já normalizados: BR + 13 dígitos (patentes e programas)
# e os antigos PI e MU + 8 dígitos. O último dígito é o verificador.
_KNOWN_FORMAT = re.compile(r"BR\d{13}|PI\d{8}|MU\d{8}")


def normalize_process_number(value: str) -> str:
    """Remove espaços, pontos e hífens e passa para maiúsculas: 'BR 10 2023 001234-5' → 'BR1020230012345'."""
    return _IGNORED_CHARACTERS.sub("", value).upper()


def has_known_format(normalized: str) -> bool:
    """Diz se o número normalizado segue um formato publicado pela RPI.

    Um número fora desses formatos (sem o "BR", sem o dígito verificador) nunca vai cruzar.
    Não há correspondência aproximada: isso serve só para avisar.
    """
    return _KNOWN_FORMAT.fullmatch(normalized) is not None
