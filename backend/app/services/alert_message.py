"""Texto do e-mail de um alerta (US11): função pura, sem acesso ao banco nem ao SMTP."""

from datetime import date

from app.models import Alert


def _format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def build_alert_email(alert: Alert) -> tuple[str, str]:
    """Monta o assunto e o corpo do e-mail de um alerta, em português simples.

    Usa o despacho, o ativo e (quando o código está no glossário) a explicação em linguagem simples.
    O alerta precisa vir com dispatch, dispatch.asset e dispatch.dispatch_code carregados.
    """
    dispatch = alert.dispatch
    asset = dispatch.asset
    process_number = asset.process_number

    if alert.requires_action and alert.deadline is not None:
        subject = f"[Radar INPI] Ação necessária até {_format_date(alert.deadline)} – {process_number}"
    elif alert.requires_action:
        subject = f"[Radar INPI] Ação necessária – {process_number}"
    else:
        subject = f"[Radar INPI] Novo despacho – {process_number}"

    lines = [
        "Olá,",
        "",
        f"O processo {process_number} ({asset.title}) teve um despacho publicado na RPI de "
        f"{_format_date(dispatch.publication_date)}.",
        "",
        f"Despacho {dispatch.code}: {dispatch.description}",
    ]
    if dispatch.dispatch_code is not None:
        lines.append(f"O que significa: {dispatch.dispatch_code.plain_description}")
    lines.append("")

    if alert.requires_action and alert.deadline is not None:
        lines.append(f"Este despacho exige ação. Prazo: {_format_date(alert.deadline)}.")
    elif alert.requires_action:
        lines.append("Este despacho exige ação. Prazo não definido; confira no sistema.")
    else:
        lines.append("Despacho apenas informativo, sem ação necessária.")

    lines += ["", "Você recebeu este aviso do Radar INPI."]
    return subject, "\n".join(lines)
