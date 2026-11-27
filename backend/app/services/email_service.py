"""Envio de e-mails dos alertas (US11), independente da camada HTTP.

Sem SMTP_HOST configurado, o e-mail só é impresso no terminal (desenvolvimento).
Uma falha de envio nunca levanta exceção: o processamento da RPI não pode parar por causa dela.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

# Remetente usado quando nem SMTP_FROM nem SMTP_USER estão configurados.
DEFAULT_SENDER = "alertas@radar-inpi.local"

SMTP_TIMEOUT_SECONDS = 10


def _sender() -> str:
    return settings.smtp_from or settings.smtp_user or DEFAULT_SENDER


def send_email(to: str, subject: str, body: str) -> bool:
    """Envia um e-mail de texto simples. Retorna True se enviou (ou imprimiu) e False se falhou."""
    if not settings.smtp_host:
        print(f"[e-mail] Para: {to}\n[e-mail] Assunto: {subject}\n{body}\n", flush=True)
        return True

    message = EmailMessage()
    message["From"] = _sender()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # OSError cobre falha de conexão e timeout. A senha nunca entra na mensagem de log.
        logger.warning(
            "Falha ao enviar e-mail para %s via %s:%s (%s)",
            to,
            settings.smtp_host,
            settings.smtp_port,
            type(exc).__name__,
        )
        return False
    return True
