"""Parser do XML da RPI (US09), com recortes reais da RPI 2916 e casos inválidos montados no teste."""

import codecs
import logging
from datetime import date
from pathlib import Path

import pytest

from app.models import AssetType
from app.models.limits import DISPATCH_DESCRIPTION_MAX_LENGTH
from app.services.rpi_errors import RpiParseError
from app.services.rpi_parser import ParsedDispatch, parse_edition, parse_rpi_file

FIXTURES = Path(__file__).parent / "fixtures" / "rpi"
PATENTES = FIXTURES / "patentes_2916.xml"
PROGRAMAS = FIXTURES / "programas_2916.xml"
EDICAO = {AssetType.PATENTE: PATENTES, AssetType.PROGRAMA_DE_COMPUTADOR: PROGRAMAS}


def _xml(despachos: str, *, numero: str = "2916", data: str = "24/11/2026", diretoria: str = "Patente") -> bytes:
    return (
        f'<revista numero="{numero}" dataPublicacao="{data}" diretoria="{diretoria}">{despachos}</revista>'
    ).encode()


def _despacho(codigo: str | None = "6.1", numero: str | None = "BR 10 2023 000001-1", titulo: str | None = "Exigência") -> str:
    partes = []
    if codigo is not None:
        partes.append(f"<codigo>{codigo}</codigo>")
    if titulo is not None:
        partes.append(f"<titulo>{titulo}</titulo>")
    processo = f"<numero>{numero}</numero>" if numero is not None else ""
    partes.append(f"<processo-patente>{processo}</processo-patente>")
    return f"<despacho>{''.join(partes)}</despacho>"


def _por_processo(despachos, numero: str) -> list[ParsedDispatch]:
    return [d for d in despachos if d.process_number == numero]


# --- Fixtures reais --------------------------------------------------------------------------------------------------


def test_le_cabecalho_e_despachos_de_patentes() -> None:
    arquivo = parse_rpi_file(PATENTES)

    assert arquivo.number == 2916
    assert arquivo.publication_date == date(2026, 11, 24)
    assert arquivo.asset_type == AssetType.PATENTE
    assert len(arquivo.dispatches) == 8
    assert arquivo.skipped == 0
    assert arquivo.dispatches[0] == ParsedDispatch(
        asset_type=AssetType.PATENTE,
        process_number="BR 12 2021 017258-7",
        code="130",
        description="Recurso Prejudicado",
        complement=(
            "Prejudicado o recurso publicado na RPI 2727 de 11/4/2023, por perda de objeto, já que o pedido foi "
            "definitivamente arquivado por falta de pagamento de retribuição anual, sendo a notificação de tal ato "
            "efetuada na RPI 2915, de 17/11/2026. [130]"
        ),
    )


def test_le_cabecalho_e_despachos_de_programas() -> None:
    arquivo = parse_rpi_file(PROGRAMAS)

    assert arquivo.asset_type == AssetType.PROGRAMA_DE_COMPUTADOR
    assert [(d.process_number, d.code) for d in arquivo.dispatches] == [
        ("BR 51 2026 009371-6", "111"),
        ("BR 51 2026 010107-7", "709"),
        ("BR 51 2026 004978-4", "730"),
    ]


def test_usa_o_numero_direto_e_nao_o_da_divisao_nem_do_pedido_principal() -> None:
    numeros = {d.process_number for d in parse_rpi_file(PATENTES).dispatches}

    assert {"BR 12 2021 017258-7", "BR 13 2025 026268-0"} <= numeros
    assert "BR 11 2018 070846-1" not in numeros  # divisao-pedido
    assert "BR 11 2018 016581-6" not in numeros  # pedido-principal


def test_usa_o_titulo_do_despacho_e_nao_o_do_processo() -> None:
    patentes = parse_rpi_file(PATENTES).dispatches
    programas = parse_rpi_file(PROGRAMAS).dispatches

    assert _por_processo(patentes, "BR 11 2024 024012-6")[0].description == "Pedido PCT Admitido na Fase Nacional"
    assert _por_processo(programas, "BR 51 2026 004978-4")[0].description == "Expedição do Certificado de Registro"


def test_ignora_codigos_aninhados_no_processo_de_programa() -> None:
    despacho = _por_processo(parse_rpi_file(PROGRAMAS).dispatches, "BR 51 2026 004978-4")[0]

    assert despacho.code == "730"  # e não IN-02 (campo de aplicação) nem AP-01 (tipo de programa)


def test_comentario_presente_vira_texto_e_ausente_vira_none() -> None:
    programas = parse_rpi_file(PROGRAMAS).dispatches

    assert programas[0].complement == "Anulado o despacho 742 publicado na RPI 2914 por ter sido indevido. ."
    assert programas[1].complement is None


def test_numeros_no_formato_antigo_sao_preservados() -> None:
    numeros = {d.process_number for d in parse_rpi_file(PATENTES).dispatches}

    assert {"PI 0002026-5", "MU 6800992-5"} <= numeros


def test_mesmo_processo_em_dois_despachos() -> None:
    despachos = _por_processo(parse_rpi_file(PATENTES).dispatches, "BR 11 2021 007863-0")

    assert [d.code for d in despachos] == ["6.1", "15.11"]


def test_codigo_longo_preservado_como_texto() -> None:
    codigos = [d.code for d in parse_rpi_file(PATENTES).dispatches]

    assert "28.10.32" in codigos
    assert "130" in codigos


def test_aceita_conteudo_em_bytes() -> None:
    assert len(parse_rpi_file(PATENTES.read_bytes()).dispatches) == 8


# --- Erros no arquivo inteiro ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "conteudo",
    [
        b"",
        _xml(_despacho())[:-30],
        b"isto nao e xml",
    ],
    ids=["vazio", "cortado", "texto"],
)
def test_xml_malformado(conteudo: bytes) -> None:
    with pytest.raises(RpiParseError, match="não é um XML válido"):
        parse_rpi_file(conteudo)


def test_recusa_doctype() -> None:
    conteudo = b'<!DOCTYPE revista [<!ENTITY x "y">]>' + _xml(_despacho())

    with pytest.raises(RpiParseError, match="DOCTYPE"):
        parse_rpi_file(conteudo)


@pytest.mark.parametrize(
    "conteudo",
    [
        _xml(_despacho(titulo="Exigência")).decode().encode("latin-1"),
        _xml(_despacho()).decode().encode("utf-16"),
        b'<?xml version="1.0" encoding="ISO-8859-1"?>' + _xml(_despacho()),
    ],
    ids=["latin-1", "utf-16", "declaracao-latin-1"],
)
def test_recusa_conteudo_que_nao_e_utf8(conteudo: bytes) -> None:
    with pytest.raises(RpiParseError, match="UTF-8"):
        parse_rpi_file(conteudo)


def test_aceita_declaracao_utf8() -> None:
    conteudo = b'<?xml version="1.0" encoding="UTF-8"?>' + _xml(_despacho())

    assert len(parse_rpi_file(conteudo).dispatches) == 1


def test_raiz_inesperada() -> None:
    with pytest.raises(RpiParseError, match="raiz é <outra>"):
        parse_rpi_file(b"<outra numero='2916'/>")


@pytest.mark.parametrize("numero", ["", "abc", "0", "-1"])
def test_numero_da_edicao_invalido(numero: str) -> None:
    with pytest.raises(RpiParseError, match="número de edição inválido"):
        parse_rpi_file(_xml(_despacho(), numero=numero))


@pytest.mark.parametrize("data", ["", "31/02/2026", "2026-11-24"])
def test_data_invalida(data: str) -> None:
    with pytest.raises(RpiParseError, match="data de publicação inválida"):
        parse_rpi_file(_xml(_despacho(), data=data))


def test_diretoria_desconhecida() -> None:
    with pytest.raises(RpiParseError, match="diretoria desconhecida"):
        parse_rpi_file(_xml(_despacho(), diretoria="Marca"))


# --- Despachos ignorados ou ajustados --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("despacho", "aviso"),
    [
        (_despacho(codigo=None), "sem código"),
        (_despacho(codigo="  "), "sem código"),
        (_despacho(codigo="1" * 11), "longo demais"),
        (_despacho(numero=None), "sem número"),
        (_despacho(numero="BR " + "9" * 60), "longo demais"),
        ("<despacho><codigo>6.1</codigo><titulo>X</titulo></despacho>", "sem número"),
    ],
    ids=["sem-codigo", "codigo-vazio", "codigo-longo", "sem-numero", "numero-longo", "sem-processo"],
)
def test_despacho_incompleto_e_ignorado_com_aviso(despacho: str, aviso: str, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.services.rpi_parser"):
        arquivo = parse_rpi_file(_xml(despacho + _despacho(numero="BR 10 2023 000002-2")))

    assert [d.process_number for d in arquivo.dispatches] == ["BR 10 2023 000002-2"]
    assert arquivo.skipped == 1
    assert aviso in caplog.text


def test_processo_de_outra_diretoria_e_ignorado() -> None:
    # Em um arquivo de programas, só <processo-programa> vale.
    arquivo = parse_rpi_file(_xml(_despacho(), diretoria="Programa"))

    assert arquivo.dispatches == ()
    assert arquivo.skipped == 1


def test_titulo_longo_e_cortado_no_limite_contando_reticencias(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.services.rpi_parser"):
        despacho = parse_rpi_file(_xml(_despacho(titulo="A" * 600))).dispatches[0]

    assert len(despacho.description) == DISPATCH_DESCRIPTION_MAX_LENGTH
    assert despacho.description.endswith("…")
    assert "cortado" in caplog.text


def test_titulo_no_limite_nao_e_cortado() -> None:
    titulo = "A" * DISPATCH_DESCRIPTION_MAX_LENGTH

    assert parse_rpi_file(_xml(_despacho(titulo=titulo))).dispatches[0].description == titulo


def test_titulo_ausente_usa_texto_padrao() -> None:
    assert parse_rpi_file(_xml(_despacho(titulo=None))).dispatches[0].description == "Despacho 6.1"


def test_espacos_extras_sao_normalizados() -> None:
    despacho = parse_rpi_file(
        _xml(_despacho(codigo=" 6.1 ", numero="  BR 10 2023 000001-1 ", titulo="Exigência \n  técnica"))
    ).dispatches[0]

    assert (despacho.code, despacho.process_number, despacho.description) == (
        "6.1",
        "BR 10 2023 000001-1",
        "Exigência técnica",
    )


def test_arquivo_sem_despachos_so_gera_aviso(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.services.rpi_parser"):
        arquivo = parse_rpi_file(_xml(""))

    assert arquivo.dispatches == ()
    assert "não tem despachos" in caplog.text


# --- parse_edition ---------------------------------------------------------------------------------------------------


def test_parse_edition_junta_patentes_e_programas() -> None:
    edicao = parse_edition(EDICAO, 2916)

    assert edicao.number == 2916
    assert edicao.publication_date == date(2026, 11, 24)
    assert len(edicao.dispatches) == 11
    assert edicao.skipped == 0
    assert edicao.dispatches[0].asset_type == AssetType.PATENTE
    assert edicao.dispatches[-1].asset_type == AssetType.PROGRAMA_DE_COMPUTADOR


def test_parse_edition_numero_diferente_do_esperado() -> None:
    with pytest.raises(RpiParseError, match="era esperada a RPI 2917"):
        parse_edition(EDICAO, 2917)


def test_parse_edition_so_um_arquivo() -> None:
    with pytest.raises(RpiParseError, match="exatamente um arquivo de patentes e um de programas"):
        parse_edition({AssetType.PATENTE: PATENTES}, 2916)


def test_parse_edition_dois_do_mesmo_tipo() -> None:
    with pytest.raises(RpiParseError, match="contém despachos de programas"):
        parse_edition({AssetType.PATENTE: PROGRAMAS, AssetType.PROGRAMA_DE_COMPUTADOR: PROGRAMAS}, 2916)


def test_parse_edition_arquivos_trocados() -> None:
    with pytest.raises(RpiParseError, match="contém despachos de programas"):
        parse_edition({AssetType.PATENTE: PROGRAMAS, AssetType.PROGRAMA_DE_COMPUTADOR: PATENTES}, 2916)


def test_parse_edition_datas_diferentes(tmp_path: Path) -> None:
    programas = tmp_path / "programas.xml"
    programas.write_bytes(PROGRAMAS.read_bytes().replace(b"24/11/2026", b"25/11/2026"))

    with pytest.raises(RpiParseError, match="datas de publicação diferentes"):
        parse_edition({AssetType.PATENTE: PATENTES, AssetType.PROGRAMA_DE_COMPUTADOR: programas}, 2916)


def test_caminho_inexistente_gera_erro_de_leitura(tmp_path: Path) -> None:
    with pytest.raises(RpiParseError, match="Não foi possível ler o arquivo nao_existe.xml") as erro:
        parse_rpi_file(tmp_path / "nao_existe.xml")

    assert isinstance(erro.value.__cause__, FileNotFoundError)


def test_parse_edition_com_arquivo_ausente(tmp_path: Path) -> None:
    with pytest.raises(RpiParseError, match="Não foi possível ler"):
        parse_edition({AssetType.PATENTE: PATENTES, AssetType.PROGRAMA_DE_COMPUTADOR: tmp_path / "x.xml"}, 2916)


def test_bom_nao_esconde_declaracao_de_outra_codificacao() -> None:
    conteudo = codecs.BOM_UTF8 + b'<?xml version="1.0" encoding="ISO-8859-1"?>' + _xml(_despacho())

    with pytest.raises(RpiParseError, match="UTF-8"):
        parse_rpi_file(conteudo)


def test_bom_com_declaracao_utf8_e_aceito() -> None:
    conteudo = codecs.BOM_UTF8 + b'<?xml version="1.0" encoding="UTF-8"?>' + _xml(_despacho())

    assert len(parse_rpi_file(conteudo).dispatches) == 1
