"""Texto do e-mail de um alerta (US11): montado sem banco, a partir de objetos em memória."""

from datetime import date

from app.models import Alert, Asset, AssetType, Dispatch, DispatchCode, User, UserRole
from app.services.alert_message import build_alert_email

PROCESSO = "BR 10 2023 000001-1"
EXPLICACAO = "O INPI pediu ajustes no pedido. É preciso responder dentro do prazo."


def _alert(*, requires_action: bool, deadline: date | None, in_glossary: bool = True) -> Alert:
    code = (
        DispatchCode(
            code="6.1",
            asset_type=AssetType.PATENTE,
            official_description="Exigência técnica",
            plain_description=EXPLICACAO,
            requires_action=requires_action,
            deadline_days=90,
        )
        if in_glossary
        else None
    )
    asset = Asset(
        title="Patente da autora",
        asset_type=AssetType.PATENTE,
        process_number=PROCESSO,
        deposit_date=date(2023, 1, 10),
        status="Em exame",
        authors="Autora Teste",
    )
    dispatch = Dispatch(
        asset=asset,
        process_number="BR102023000001-1",  # como veio na RPI; o e-mail usa o número cadastrado
        code="6.1",
        dispatch_code=code,
        description="Exigência técnica",
        publication_date=date(2026, 11, 24),
    )
    user = User(email="autora@teste.edu.br", hashed_password="x", role=UserRole.AUTOR)
    return Alert(user=user, dispatch=dispatch, requires_action=requires_action, deadline=deadline)


def test_exige_acao_com_prazo() -> None:
    subject, body = build_alert_email(_alert(requires_action=True, deadline=date(2027, 2, 22)))

    assert subject == f"[Radar INPI] Ação necessária até 22/02/2027 – {PROCESSO}"
    assert body == (
        "Olá,\n"
        "\n"
        f"O processo {PROCESSO} (Patente da autora) teve um despacho publicado na RPI de 24/11/2026.\n"
        "\n"
        "Despacho 6.1: Exigência técnica\n"
        f"O que significa: {EXPLICACAO}\n"
        "\n"
        "Este despacho exige ação. Prazo: 22/02/2027.\n"
        "\n"
        "Você recebeu este aviso do Radar INPI."
    )


def test_exige_acao_sem_prazo_definido() -> None:
    subject, body = build_alert_email(_alert(requires_action=True, deadline=None))

    assert subject == f"[Radar INPI] Ação necessária – {PROCESSO}"
    assert "Este despacho exige ação. Prazo não definido; confira no sistema." in body
    assert "Prazo: " not in body


def test_informativo() -> None:
    subject, body = build_alert_email(_alert(requires_action=False, deadline=None))

    assert subject == f"[Radar INPI] Novo despacho – {PROCESSO}"
    assert "Despacho apenas informativo, sem ação necessária." in body
    assert "exige ação" not in body


def test_codigo_fora_do_glossario_nao_tem_explicacao() -> None:
    subject, body = build_alert_email(_alert(requires_action=False, deadline=None, in_glossary=False))

    assert subject == f"[Radar INPI] Novo despacho – {PROCESSO}"
    assert "Despacho 6.1: Exigência técnica" in body
    assert "O que significa" not in body


def test_usa_o_numero_cadastrado_e_termina_com_a_assinatura() -> None:
    _subject, body = build_alert_email(_alert(requires_action=False, deadline=None))

    assert PROCESSO in body
    assert "BR102023000001-1" not in body
    assert body.endswith("Você recebeu este aviso do Radar INPI.")
