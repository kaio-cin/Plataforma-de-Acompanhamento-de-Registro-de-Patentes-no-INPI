"""Envio de e-mail dos alertas (US11): terminal em desenvolvimento, SMTP em produção, sem nunca derrubar a aplicação."""

import logging
import smtplib
from email.message import EmailMessage

import pytest

from app.core.config import settings
from app.services.email_service import SMTP_TIMEOUT_SECONDS, send_email

DESTINATARIO = "autora@teste.edu.br"
ASSUNTO = "Novo despacho na RPI"
CORPO = "O processo BR 10 2023 000001-1 recebeu o despacho 6.1."


class FakeSMTP:
    """Substitui smtplib.SMTP: registra as chamadas e nunca abre conexão de rede."""

    instances: list["FakeSMTP"] = []
    error: Exception | None = None

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.calls: list[str] = []
        self.sent: list[EmailMessage] = []
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, user: str, _password: str) -> None:
        self.calls.append("login")
        self.user = user

    def send_message(self, message: EmailMessage) -> None:
        if FakeSMTP.error is not None:
            raise FakeSMTP.error
        self.calls.append("send_message")
        self.sent.append(message)


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSMTP]:
    """SMTP configurado e falso. Fixa todas as settings para o teste não depender do .env local."""
    FakeSMTP.instances = []
    FakeSMTP.error = None
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_host", "smtp.teste.local")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "nit@teste.edu.br")
    monkeypatch.setattr(settings, "smtp_password", "senha-de-app")
    monkeypatch.setattr(settings, "smtp_from", "")
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    return FakeSMTP


def unica_conexao(fake: type[FakeSMTP]) -> FakeSMTP:
    assert len(fake.instances) == 1
    return fake.instances[0]


def test_sem_smtp_host_imprime_no_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], fake_smtp: type[FakeSMTP]
) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")

    assert send_email(DESTINATARIO, ASSUNTO, CORPO) is True

    saida = capsys.readouterr().out
    assert DESTINATARIO in saida and ASSUNTO in saida and CORPO in saida
    assert fake_smtp.instances == []


def test_envia_com_starttls_e_login(fake_smtp: type[FakeSMTP]) -> None:
    assert send_email(DESTINATARIO, ASSUNTO, CORPO) is True

    conexao = unica_conexao(fake_smtp)
    assert (conexao.host, conexao.port, conexao.timeout) == ("smtp.teste.local", 587, SMTP_TIMEOUT_SECONDS)
    assert conexao.calls == ["starttls", "login", "send_message"]
    assert conexao.user == "nit@teste.edu.br"
    mensagem = conexao.sent[0]
    assert mensagem["To"] == DESTINATARIO
    assert mensagem["Subject"] == ASSUNTO
    assert mensagem.get_content().strip() == CORPO


def test_sem_smtp_user_nao_faz_login(monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]) -> None:
    monkeypatch.setattr(settings, "smtp_user", "")

    assert send_email(DESTINATARIO, ASSUNTO, CORPO) is True

    assert "login" not in unica_conexao(fake_smtp).calls


def test_sem_tls_nao_chama_starttls(monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]) -> None:
    monkeypatch.setattr(settings, "smtp_use_tls", False)

    assert send_email(DESTINATARIO, ASSUNTO, CORPO) is True

    assert "starttls" not in unica_conexao(fake_smtp).calls


@pytest.mark.parametrize(
    ("smtp_from", "smtp_user", "remetente_esperado"),
    [
        ("radar@instituicao.edu.br", "nit@teste.edu.br", "radar@instituicao.edu.br"),
        ("", "nit@teste.edu.br", "nit@teste.edu.br"),
        ("", "", "alertas@radar-inpi.local"),
    ],
)
def test_ordem_de_escolha_do_remetente(
    monkeypatch: pytest.MonkeyPatch,
    fake_smtp: type[FakeSMTP],
    smtp_from: str,
    smtp_user: str,
    remetente_esperado: str,
) -> None:
    monkeypatch.setattr(settings, "smtp_from", smtp_from)
    monkeypatch.setattr(settings, "smtp_user", smtp_user)

    assert send_email(DESTINATARIO, ASSUNTO, CORPO) is True

    assert unica_conexao(fake_smtp).sent[0]["From"] == remetente_esperado


@pytest.mark.parametrize(
    "erro",
    [smtplib.SMTPException("servidor recusou"), OSError("conexão recusada")],
    ids=["SMTPException", "OSError"],
)
def test_erro_de_envio_retorna_false_sem_excecao(fake_smtp: type[FakeSMTP], erro: Exception) -> None:
    fake_smtp.error = erro

    assert send_email(DESTINATARIO, ASSUNTO, CORPO) is False


def test_senha_nao_aparece_no_log_quando_o_envio_falha(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    fake_smtp: type[FakeSMTP],
) -> None:
    monkeypatch.setattr(settings, "smtp_password", "segredo123")
    # Pior caso: o próprio erro do servidor repete a senha na mensagem.
    fake_smtp.error = smtplib.SMTPAuthenticationError(535, b"credencial segredo123 rejeitada")

    with caplog.at_level(logging.DEBUG):
        assert send_email(DESTINATARIO, ASSUNTO, CORPO) is False

    assert caplog.records, "a falha deveria ser registrada no log"
    assert any(record.levelno == logging.WARNING for record in caplog.records)
    assert "segredo123" not in caplog.text
    saida = capsys.readouterr()
    assert "segredo123" not in saida.out and "segredo123" not in saida.err
