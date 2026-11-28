"""Criação de usuários pela equipe técnica: regra em user_service e comando python -m app.create_user."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import create_user as comando
from app.models import User, UserRole
from app.models.limits import EMAIL_MAX_LENGTH
from app.services import user_service
from app.services.user_service import InvalidUserDataError, UserAlreadyExistsError

SENHA = "senha-forte-1"


def _total_users(db_session: Session) -> int:
    return db_session.scalar(select(func.count(User.id)))


# --- user_service.create_user ----------------------------------------------------------------------------------------


def test_cria_usuario_com_senha_em_hash(db_session: Session) -> None:
    user = user_service.create_user(db_session, "nit@ufca.edu.br", SENHA, UserRole.NIT)

    assert (user.email, user.role) == ("nit@ufca.edu.br", UserRole.NIT)
    assert user.hashed_password != SENHA
    assert _total_users(db_session) == 1


def test_guarda_o_email_como_o_login_procura(db_session: Session) -> None:
    user = user_service.create_user(db_session, "  Fulana.Silva@UFCA.edu.br ", SENHA, UserRole.AUTOR)

    assert user.email == "fulana.silva@ufca.edu.br"


def test_usuario_criado_consegue_entrar(client: TestClient, db_session: Session) -> None:
    user_service.create_user(db_session, "Nit@UFCA.edu.br", SENHA, UserRole.NIT)

    response = client.post("/api/auth/login", json={"email": "nit@ufca.edu.br", "password": SENHA})

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "NIT"


def test_recusa_email_ja_cadastrado_sem_diferenciar_maiusculas(db_session: Session) -> None:
    user_service.create_user(db_session, "nit@ufca.edu.br", SENHA, UserRole.NIT)

    with pytest.raises(UserAlreadyExistsError):
        user_service.create_user(db_session, "NIT@ufca.edu.br", "outra-senha-1", UserRole.AUTOR)
    assert _total_users(db_session) == 1


@pytest.mark.parametrize("email", ["", "sem-arroba", "nit@", "@ufca.edu.br", "nit @ufca.edu.br"])
def test_recusa_email_invalido(db_session: Session, email: str) -> None:
    with pytest.raises(InvalidUserDataError):
        user_service.create_user(db_session, email, SENHA, UserRole.NIT)
    assert _total_users(db_session) == 0


def test_recusa_email_maior_que_a_coluna(db_session: Session) -> None:
    email = "a" * EMAIL_MAX_LENGTH + "@ufca.edu.br"

    with pytest.raises(InvalidUserDataError):
        user_service.create_user(db_session, email, SENHA, UserRole.NIT)


@pytest.mark.parametrize(
    "senha",
    [
        "curta1",  # menos de 8 caracteres
        "        ",  # só espaços
        "é" * 37,  # 37 caracteres, mas 74 bytes: passa do limite do bcrypt
    ],
)
def test_recusa_senha_fora_das_regras(db_session: Session, senha: str) -> None:
    with pytest.raises(InvalidUserDataError):
        user_service.create_user(db_session, "nit@ufca.edu.br", senha, UserRole.NIT)
    assert _total_users(db_session) == 0


def test_aceita_senha_no_limite(db_session: Session) -> None:
    user_service.create_user(db_session, "a@ufca.edu.br", "x" * user_service.MIN_PASSWORD_LENGTH, UserRole.NIT)
    user_service.create_user(db_session, "b@ufca.edu.br", "x" * user_service.MAX_PASSWORD_BYTES, UserRole.NIT)

    assert _total_users(db_session) == 2


# --- Comando python -m app.create_user -------------------------------------------------------------------------------


@pytest.fixture
def banco_do_teste(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """Faz o comando usar o banco em memória do teste, nunca o banco real."""
    monkeypatch.setattr(comando, "init_db", lambda: None)
    monkeypatch.setattr(comando, "SessionLocal", lambda: db_session)
    return db_session


def _digita(*respostas: str) -> Callable[[str], str]:
    fila = list(respostas)
    return lambda _prompt: fila.pop(0)


def test_comando_cria_o_usuario(banco_do_teste: Session, capsys: pytest.CaptureFixture[str]) -> None:
    comando.main(["--email", "nit@ufca.edu.br", "--perfil", "NIT"], read_password=_digita(SENHA, SENHA))

    saida = capsys.readouterr().out
    assert "Usuário criado: nit@ufca.edu.br (NIT)." in saida
    assert SENHA not in saida
    assert _total_users(banco_do_teste) == 1


def test_comando_mostra_o_banco_sem_a_senha(
    banco_do_teste: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(comando.settings, "database_url", "postgresql+psycopg://radar:segredo@host:5432/radar")

    comando.main(["--email", "nit@ufca.edu.br", "--perfil", "NIT"], read_password=_digita(SENHA, SENHA))

    saida = capsys.readouterr().out
    assert "Banco: postgresql+psycopg://radar:***@host:5432/radar" in saida
    assert "segredo" not in saida


def test_comando_recusa_senhas_diferentes(banco_do_teste: Session, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        comando.main(["--email", "nit@ufca.edu.br", "--perfil", "NIT"], read_password=_digita(SENHA, "outra-senha"))

    assert exc_info.value.code == 1
    assert "não conferem" in capsys.readouterr().out
    assert _total_users(banco_do_teste) == 0


def test_comando_explica_o_erro_sem_criar(banco_do_teste: Session, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        comando.main(["--email", "nit@ufca.edu.br", "--perfil", "NIT"], read_password=_digita("curta", "curta"))

    assert exc_info.value.code == 1
    assert "pelo menos 8 caracteres" in capsys.readouterr().out
    assert _total_users(banco_do_teste) == 0


@pytest.mark.parametrize("argv", [["--email", "nit@ufca.edu.br"], ["--email", "x@y.br", "--perfil", "ADMIN"]])
def test_comando_exige_perfil_valido(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        comando.main(argv, read_password=_digita(SENHA, SENHA))

    assert exc_info.value.code == 2  # argparse: argumento ausente ou inválido
