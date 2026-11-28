"""Normalização do número do processo usada no cruzamento com a RPI (US09)."""

import pytest

from app.services.process_number import has_known_format, normalize_process_number


@pytest.mark.parametrize(
    ("cadastrado", "esperado"),
    [
        ("BR 10 2023 001234-5", "BR1020230012345"),
        ("BR10.2023.001234-5", "BR1020230012345"),
        ("br 10 2023 001234 5", "BR1020230012345"),
        ("  BR\t10 2023\n001234-5 ", "BR1020230012345"),
        ("BR 51 2026 004978-4", "BR5120260049784"),
        ("PI 0002026-5", "PI00020265"),
        ("pi0002026-5", "PI00020265"),
        ("MU 6800992-5", "MU68009925"),
    ],
)
def test_remove_espacos_pontos_e_hifens_e_passa_para_maiusculas(cadastrado: str, esperado: str) -> None:
    assert normalize_process_number(cadastrado) == esperado


def test_formatos_equivalentes_geram_a_mesma_chave() -> None:
    variantes = ["BR 11 2021 007863-0", "BR11 2021 007863-0", "BR11.2021.007863-0", "br112021007863-0"]

    assert len({normalize_process_number(v) for v in variantes}) == 1


@pytest.mark.parametrize("numero", ["BR1020230012345", "PI00020265", "MU68009925"])
def test_formatos_conhecidos(numero: str) -> None:
    assert has_known_format(numero)


@pytest.mark.parametrize(
    ("cadastrado", "publicado_na_rpi"),
    [
        ("10 2023 001234-5", "BR 10 2023 001234-5"),  # sem o "BR"
        ("BR 10 2023 001234", "BR 10 2023 001234-5"),  # sem o dígito verificador
    ],
)
def test_numero_incompleto_nao_cruza_e_e_sinalizado(cadastrado: str, publicado_na_rpi: str) -> None:
    # Risco documentado: sem correspondência aproximada, esses cadastros nunca recebem despachos.
    assert normalize_process_number(cadastrado) != normalize_process_number(publicado_na_rpi)
    assert not has_known_format(normalize_process_number(cadastrado))
