"""Download dos arquivos da RPI (US08), sem internet: urlopen é substituído por respostas falsas."""

import http.client
import io
import logging
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from email.message import Message
from pathlib import Path

import pytest

from app.models import AssetType
from app.services import rpi_download_service as service
from app.services.rpi_download_service import DEFAULT_DATA_DIR, download_edition, file_url
from app.services.rpi_errors import RpiDownloadError, RpiInvalidFileError, RpiNotPublishedError

URL_PATENTES = "https://revistas.inpi.gov.br/txt/P2916.zip"
URL_PROGRAMAS = "https://revistas.inpi.gov.br/txt/PC2916.zip"
XML_PATENTES = b'<revista numero="2916" diretoria="Patente"/>'
XML_PROGRAMAS = b'<revista numero="2916" diretoria="Programa"/>'


def _zip(members: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


ZIP_PATENTES = _zip({"P2916.txt": b"texto", "Patente_2916_24112026.xml": XML_PATENTES})
ZIP_PROGRAMAS = _zip({"Programa_2916.txt": b"texto", "Programa_2916_24112026.xml": XML_PROGRAMAS})


class FakeResponse:
    """Imita a resposta do urlopen: geturl(), headers, read(n) e uso com "with"."""

    def __init__(
        self,
        body: bytes,
        *,
        url: str = "",
        content_type: str = "application/zip",
        content_length: int | None = -1,
    ) -> None:
        self._body = io.BytesIO(body)
        self._url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        length = len(body) if content_length == -1 else content_length
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


Resposta = FakeResponse | Exception | Callable[[str], FakeResponse]


class FakeInternet:
    """Fila de respostas por URL. Registra cada chamada; nunca abre conexão de rede."""

    def __init__(self) -> None:
        self.queues: dict[str, list[Resposta]] = {}
        self.calls: list[str] = []
        self.headers: list[dict[str, str]] = []

    def queue(self, url: str, *responses: Resposta) -> None:
        self.queues.setdefault(url, []).extend(responses)

    def urlopen(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        url = request.full_url
        self.calls.append(url)
        self.headers.append(dict(request.header_items()))
        assert timeout == service.TIMEOUT_SECONDS
        response = self.queues[url].pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response) and not isinstance(response, FakeResponse):
            return response(url)
        if not response.geturl():
            response._url = url
        return response

    def count(self, url: str) -> int:
        return self.calls.count(url)


@pytest.fixture
def internet(monkeypatch: pytest.MonkeyPatch) -> FakeInternet:
    fake = FakeInternet()
    monkeypatch.setattr(urllib.request, "urlopen", fake.urlopen)
    return fake


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Substitui time.sleep para os testes de nova tentativa não esperarem."""
    registro: list[float] = []
    monkeypatch.setattr(time, "sleep", registro.append)
    return registro


def _ok(body: bytes = ZIP_PATENTES) -> FakeResponse:
    return FakeResponse(body)


def _http_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "erro", Message(), None)


def _nao_publicado(_url: str) -> FakeResponse:
    return FakeResponse(
        b"<html>Pagina nao encontrada</html>",
        url="https://revistas.inpi.gov.br/error/404.html",
        content_type="text/html",
    )


def _arquivos(pasta: Path) -> list[str]:
    return sorted(p.name for p in pasta.rglob("*") if p.is_file())


# --- Caminho feliz ---------------------------------------------------------------------------------------------------


def test_monta_as_urls_da_edicao() -> None:
    patentes, programas = service.RPI_FILES

    assert file_url(patentes, 2916) == URL_PATENTES
    assert file_url(programas, 2916) == URL_PROGRAMAS


def test_pasta_padrao_e_backend_data_rpi() -> None:
    assert DEFAULT_DATA_DIR == Path(service.__file__).resolve().parents[2] / "data" / "rpi"
    assert DEFAULT_DATA_DIR.parts[-3:] == ("backend", "data", "rpi")


def test_baixa_e_extrai_os_dois_xml(internet: FakeInternet, tmp_path: Path) -> None:
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    caminhos = download_edition(2916, tmp_path)

    assert caminhos == {
        AssetType.PATENTE: tmp_path / "2916" / "patentes.xml",
        AssetType.PROGRAMA_DE_COMPUTADOR: tmp_path / "2916" / "programas.xml",
    }
    assert caminhos[AssetType.PATENTE].read_bytes() == XML_PATENTES
    assert caminhos[AssetType.PROGRAMA_DE_COMPUTADOR].read_bytes() == XML_PROGRAMAS
    # Nem o ZIP, nem o .txt, nem temporários ficam no disco.
    assert _arquivos(tmp_path) == ["patentes.xml", "programas.xml"]


def test_envia_user_agent_generico(internet: FakeInternet, tmp_path: Path) -> None:
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    download_edition(2916, tmp_path)

    assert all(h.get("User-agent") == "RadarINPI/1.0" for h in internet.headers)


def test_nome_dentro_do_zip_nao_vira_caminho(internet: FakeInternet, tmp_path: Path) -> None:
    data_dir = tmp_path / "dados"
    internet.queue(URL_PATENTES, _ok(_zip({"../../evil.xml": XML_PATENTES})))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    download_edition(2916, data_dir)

    assert (data_dir / "2916" / "patentes.xml").read_bytes() == XML_PATENTES
    assert "evil.xml" not in _arquivos(tmp_path)


def test_arquivo_existente_nao_e_baixado_de_novo(internet: FakeInternet, tmp_path: Path) -> None:
    pasta = tmp_path / "2916"
    pasta.mkdir()
    (pasta / "patentes.xml").write_bytes(b"antigo")
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    download_edition(2916, tmp_path)

    assert internet.calls == [URL_PROGRAMAS]
    assert (pasta / "patentes.xml").read_bytes() == b"antigo"


def test_force_baixa_de_novo(internet: FakeInternet, tmp_path: Path) -> None:
    pasta = tmp_path / "2916"
    pasta.mkdir()
    (pasta / "patentes.xml").write_bytes(b"antigo")
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    download_edition(2916, tmp_path, force=True)

    assert (pasta / "patentes.xml").read_bytes() == XML_PATENTES


@pytest.mark.parametrize("numero", [0, -1])
def test_numero_de_edicao_invalido(numero: int, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        download_edition(numero, tmp_path)


# --- Edição não publicada --------------------------------------------------------------------------------------------


def test_redirecionamento_para_404_html_e_edicao_nao_publicada(
    internet: FakeInternet, sleeps: list[float], tmp_path: Path
) -> None:
    internet.queue(URL_PATENTES, _nao_publicado)

    with pytest.raises(RpiNotPublishedError, match="RPI 2916 ainda não foi publicada"):
        download_edition(2916, tmp_path)

    assert internet.calls == [URL_PATENTES]  # uma tentativa só, e programas nem é tentado
    assert sleeps == []
    assert not (tmp_path / "2916").exists()  # não sobra pasta vazia


def test_http_404_e_edicao_nao_publicada(internet: FakeInternet, sleeps: list[float], tmp_path: Path) -> None:
    internet.queue(URL_PATENTES, _http_error(URL_PATENTES, 404))

    with pytest.raises(RpiNotPublishedError):
        download_edition(2916, tmp_path)

    assert internet.calls == [URL_PATENTES]


# --- Novas tentativas ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "falha",
    [
        urllib.error.URLError("sem rede"),
        TimeoutError("timeout"),
        ConnectionResetError("conexão caiu"),
        http.client.IncompleteRead(b"parcial"),
        _http_error(URL_PATENTES, 503),
        FakeResponse(b"<html>manutencao</html>", content_type="text/html; charset=utf-8"),
        FakeResponse(ZIP_PATENTES[:100], content_length=len(ZIP_PATENTES)),
        # ZIP válido, mas menor que o anunciado: só a conferência do Content-Length percebe.
        FakeResponse(ZIP_PATENTES, content_length=len(ZIP_PATENTES) + 10),
    ],
    ids=["url-error", "timeout", "conexao", "http-exception", "http-503", "html", "cortado", "content-length"],
)
def test_falha_passageira_seguida_de_sucesso(
    falha: Resposta, internet: FakeInternet, sleeps: list[float], tmp_path: Path
) -> None:
    internet.queue(URL_PATENTES, falha, _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    caminhos = download_edition(2916, tmp_path)

    assert internet.count(URL_PATENTES) == 2
    assert sleeps == [2]
    assert caminhos[AssetType.PATENTE].read_bytes() == XML_PATENTES


def test_tres_falhas_de_rede_geram_erro_de_download(
    internet: FakeInternet, sleeps: list[float], tmp_path: Path
) -> None:
    internet.queue(URL_PATENTES, *(urllib.error.URLError("sem rede") for _ in range(3)))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    with pytest.raises(RpiDownloadError, match="após 3 tentativas") as erro:
        download_edition(2916, tmp_path)

    assert type(erro.value) is RpiDownloadError
    assert internet.count(URL_PATENTES) == 3
    assert sleeps == [2, 4]


def test_html_tres_vezes_gera_erro_de_download(internet: FakeInternet, sleeps: list[float], tmp_path: Path) -> None:
    html = [FakeResponse(b"<html/>", content_type="text/html") for _ in range(3)]
    internet.queue(URL_PATENTES, *html)
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    with pytest.raises(RpiDownloadError) as erro:
        download_edition(2916, tmp_path)

    assert type(erro.value) is RpiDownloadError


@pytest.mark.parametrize("codigo", [400, 403])
def test_outro_erro_4xx_nao_e_repetido(
    codigo: int, internet: FakeInternet, sleeps: list[float], tmp_path: Path
) -> None:
    internet.queue(URL_PATENTES, _http_error(URL_PATENTES, codigo))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    with pytest.raises(RpiDownloadError, match=f"HTTP {codigo}"):
        download_edition(2916, tmp_path)

    assert internet.count(URL_PATENTES) == 1


# --- ZIP inválido ----------------------------------------------------------------------------------------------------


def _zip_com_crc_errado() -> bytes:
    conteudo = _zip({"Patente.xml": XML_PATENTES}, compression=zipfile.ZIP_STORED)
    # Troca um byte do XML guardado sem compressão: o CRC deixa de bater.
    posicao = conteudo.index(XML_PATENTES)
    return conteudo[:posicao] + b"X" + conteudo[posicao + 1 :]


@pytest.mark.parametrize(
    "corrompido",
    [_zip_com_crc_errado(), ZIP_PATENTES[:-30], b"nao e um zip"],
    ids=["crc", "cortado", "lixo"],
)
def test_tres_zips_corrompidos_geram_arquivo_invalido(
    corrompido: bytes, internet: FakeInternet, sleeps: list[float], tmp_path: Path
) -> None:
    internet.queue(URL_PATENTES, *(FakeResponse(corrompido) for _ in range(3)))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    with pytest.raises(RpiInvalidFileError, match="incompleto ou corrompido"):
        download_edition(2916, tmp_path)

    assert internet.count(URL_PATENTES) == 3
    # O arquivo de programas deu certo e fica; de patentes, nem final nem temporário.
    assert _arquivos(tmp_path) == ["programas.xml"]


def test_zip_corrompido_seguido_de_zip_bom(internet: FakeInternet, sleeps: list[float], tmp_path: Path) -> None:
    internet.queue(URL_PATENTES, FakeResponse(_zip_com_crc_errado()), _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    download_edition(2916, tmp_path)

    assert internet.count(URL_PATENTES) == 2


@pytest.mark.parametrize(
    "membros",
    [{"P2916.txt": b"texto"}, {"a.xml": XML_PATENTES, "b.XML": XML_PATENTES}],
    ids=["sem-xml", "dois-xml"],
)
def test_zip_sem_exatamente_um_xml(membros: dict[str, bytes], internet: FakeInternet, tmp_path: Path) -> None:
    internet.queue(URL_PATENTES, _ok(_zip(membros)))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    with pytest.raises(RpiInvalidFileError, match="formato esperado"):
        download_edition(2916, tmp_path)

    assert internet.count(URL_PATENTES) == 1
    assert _arquivos(tmp_path) == ["programas.xml"]


@pytest.mark.parametrize(
    ("limite", "valor"),
    [("MAX_MEMBER_BYTES", 10), ("MAX_TOTAL_UNCOMPRESSED_BYTES", len(XML_PATENTES) + 1)],
    ids=["por-membro", "soma"],
)
def test_membro_acima_do_limite_e_recusado_antes_do_testzip(
    limite: str, valor: int, internet: FakeInternet, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    chamadas: list[str] = []
    monkeypatch.setattr(service, limite, valor)
    monkeypatch.setattr(zipfile.ZipFile, "testzip", lambda self: chamadas.append("testzip"))
    internet.queue(URL_PATENTES, _ok(_zip({"P2916.txt": b"texto", "Patente.xml": XML_PATENTES})))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    with pytest.raises(RpiInvalidFileError, match="tamanho máximo"):
        download_edition(2916, tmp_path)

    assert chamadas == []  # os dois ZIPs foram recusados sem chegar ao testzip()
    assert internet.count(URL_PATENTES) == 1
    assert "patentes.xml" not in _arquivos(tmp_path)


def test_zip_acima_do_limite_e_recusado(
    internet: FakeInternet, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(service, "MAX_ZIP_BYTES", 50)
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    with pytest.raises(RpiInvalidFileError, match="tamanho máximo"):
        download_edition(2916, tmp_path)

    assert _arquivos(tmp_path) == []


# --- Um arquivo falha, o outro funciona ------------------------------------------------------------------------------


def test_falha_em_um_arquivo_mantem_o_outro_e_a_edicao_falha(
    internet: FakeInternet, sleeps: list[float], tmp_path: Path
) -> None:
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, *(urllib.error.URLError("sem rede") for _ in range(3)))

    with pytest.raises(RpiDownloadError, match="programas da RPI 2916"):
        download_edition(2916, tmp_path)

    assert _arquivos(tmp_path) == ["patentes.xml"]

    # Na próxima vez, só o que falta é baixado.
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))
    download_edition(2916, tmp_path)

    assert internet.count(URL_PATENTES) == 1
    assert _arquivos(tmp_path) == ["patentes.xml", "programas.xml"]


# --- Falha no disco local --------------------------------------------------------------------------------------------


def _replace_que_falha(monkeypatch: pytest.MonkeyPatch, vezes: int | None) -> list[str]:
    """Faz os.replace levantar PermissionError nas primeiras `vezes` chamadas (None = sempre)."""
    chamadas: list[str] = []
    original = service.os.replace

    def replace(origem, destino) -> None:
        chamadas.append(str(destino))
        if vezes is None or len(chamadas) <= vezes:
            raise PermissionError("arquivo bloqueado por outro programa")
        original(origem, destino)

    monkeypatch.setattr(service.os, "replace", replace)
    return chamadas


def test_falha_ao_renomear_uma_vez_funciona_na_segunda_tentativa(
    internet: FakeInternet, sleeps: list[float], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _replace_que_falha(monkeypatch, vezes=1)
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES), _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    caminhos = download_edition(2916, tmp_path)

    assert internet.count(URL_PATENTES) == 2
    assert sleeps == [2]
    assert caminhos[AssetType.PATENTE].read_bytes() == XML_PATENTES
    assert _arquivos(tmp_path) == ["patentes.xml", "programas.xml"]


def test_falha_ao_renomear_sempre_gera_erro_e_tenta_o_outro_arquivo(
    internet: FakeInternet, sleeps: list[float], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _replace_que_falha(monkeypatch, vezes=None)
    internet.queue(URL_PATENTES, *(_ok(ZIP_PATENTES) for _ in range(3)))
    internet.queue(URL_PROGRAMAS, *(_ok(ZIP_PROGRAMAS) for _ in range(3)))

    with pytest.raises(RpiDownloadError, match="baixar ou salvar o arquivo de patentes") as erro:
        download_edition(2916, tmp_path)

    assert type(erro.value) is RpiDownloadError
    # A causa original fica encadeada: erro de disco interno → PermissionError.
    assert isinstance(erro.value.__cause__.__cause__, PermissionError)
    assert internet.count(URL_PATENTES) == 3
    assert internet.count(URL_PROGRAMAS) == 3  # o segundo arquivo também foi tentado
    assert _arquivos(tmp_path) == []  # nem arquivo final, nem temporário


def test_falha_ao_criar_temporario_tem_nova_tentativa(
    internet: FakeInternet, sleeps: list[float], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = service.tempfile.mkstemp
    falhas = iter([True])

    def mkstemp(*args, **kwargs):
        if next(falhas, False):
            raise OSError("disco cheio")
        return original(*args, **kwargs)

    monkeypatch.setattr(service.tempfile, "mkstemp", mkstemp)
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    download_edition(2916, tmp_path)

    assert sleeps == [2]
    assert _arquivos(tmp_path) == ["patentes.xml", "programas.xml"]


def test_falha_ao_criar_a_pasta_da_edicao(
    internet: FakeInternet, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def mkdir(self, *args, **kwargs) -> None:
        raise PermissionError("sem permissão")

    monkeypatch.setattr(Path, "mkdir", mkdir)

    with pytest.raises(RpiDownloadError, match="não foi possível criar a pasta") as erro:
        download_edition(2916, tmp_path)

    assert isinstance(erro.value.__cause__, PermissionError)
    assert internet.calls == []


def test_falha_na_limpeza_nao_esconde_o_erro_original(
    internet: FakeInternet,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    _replace_que_falha(monkeypatch, vezes=None)

    def unlink(self, missing_ok: bool = False) -> None:
        raise PermissionError("não deu para apagar")

    monkeypatch.setattr(Path, "unlink", unlink)
    internet.queue(URL_PATENTES, *(_ok(ZIP_PATENTES) for _ in range(3)))
    internet.queue(URL_PROGRAMAS, *(_ok(ZIP_PROGRAMAS) for _ in range(3)))

    with caplog.at_level(logging.WARNING, logger="app.services.rpi_download_service"):
        with pytest.raises(RpiDownloadError, match="baixar ou salvar"):
            download_edition(2916, tmp_path)

    assert "Não foi possível apagar o arquivo temporário" in caplog.text


class _ArquivoQueFalhaAoFechar:
    """Embrulha o arquivo real: grava normalmente, mas o fechamento levanta OSError (disco cheio)."""

    def __init__(self, real) -> None:
        self._real = real

    def write(self, dados: bytes) -> int:
        return self._real.write(dados)

    def __enter__(self) -> "_ArquivoQueFalhaAoFechar":
        return self

    def __exit__(self, *_exc: object) -> None:
        self._real.close()  # fecha de verdade, para o temporário poder ser apagado
        raise OSError(28, "No space left on device")


def _fechamento_que_falha(monkeypatch: pytest.MonkeyPatch, vezes: int | None) -> list[int]:
    """Faz o fechamento do arquivo aberto por os.fdopen falhar nas primeiras `vezes` chamadas (None = sempre)."""
    chamadas: list[int] = []
    original = service.os.fdopen

    def fdopen(fd: int, *args, **kwargs):
        chamadas.append(fd)
        real = original(fd, *args, **kwargs)
        if vezes is None or len(chamadas) <= vezes:
            return _ArquivoQueFalhaAoFechar(real)
        return real

    monkeypatch.setattr(service.os, "fdopen", fdopen)
    return chamadas


def test_falha_ao_fechar_o_zip_temporario_funciona_na_segunda_tentativa(
    internet: FakeInternet, sleeps: list[float], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fechamento_que_falha(monkeypatch, vezes=1)
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES), _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    caminhos = download_edition(2916, tmp_path)

    assert internet.count(URL_PATENTES) == 2
    assert sleeps == [2]
    assert caminhos[AssetType.PATENTE].read_bytes() == XML_PATENTES
    assert _arquivos(tmp_path) == ["patentes.xml", "programas.xml"]  # nenhum temporário sobrou


def test_falha_ao_fechar_o_zip_temporario_sempre_gera_erro(
    internet: FakeInternet, sleeps: list[float], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fechamento_que_falha(monkeypatch, vezes=None)
    internet.queue(URL_PATENTES, *(_ok(ZIP_PATENTES) for _ in range(3)))
    internet.queue(URL_PROGRAMAS, *(_ok(ZIP_PROGRAMAS) for _ in range(3)))

    with pytest.raises(RpiDownloadError, match="baixar ou salvar o arquivo de patentes") as erro:
        download_edition(2916, tmp_path)

    assert type(erro.value) is RpiDownloadError
    assert isinstance(erro.value.__cause__.__cause__, OSError)
    assert internet.count(URL_PATENTES) == 3
    assert internet.count(URL_PROGRAMAS) == 3
    assert _arquivos(tmp_path) == []


def test_falha_no_fdopen_fecha_o_descritor_e_tenta_de_novo(
    internet: FakeInternet, sleeps: list[float], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original_fdopen, original_close = service.os.fdopen, service.os.close
    falhas = iter([True])
    fechados: list[int] = []

    def fdopen(fd: int, *args, **kwargs):
        if next(falhas, False):
            raise OSError("sem memória para o buffer")
        return original_fdopen(fd, *args, **kwargs)

    def close(fd: int) -> None:
        fechados.append(fd)
        original_close(fd)

    monkeypatch.setattr(service.os, "fdopen", fdopen)
    monkeypatch.setattr(service.os, "close", close)
    internet.queue(URL_PATENTES, _ok(ZIP_PATENTES))
    internet.queue(URL_PROGRAMAS, _ok(ZIP_PROGRAMAS))

    download_edition(2916, tmp_path)

    assert len(fechados) == 1  # o descritor do mkstemp foi fechado
    assert sleeps == [2]
    # No Windows, um descritor esquecido aberto impediria apagar o temporário.
    assert _arquivos(tmp_path) == ["patentes.xml", "programas.xml"]
