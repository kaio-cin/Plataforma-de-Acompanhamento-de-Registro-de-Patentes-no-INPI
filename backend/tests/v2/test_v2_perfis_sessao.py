"""Testes de perfis de acesso e sessão — US02 e US03.

Técnicas: critérios de aceitação (CA), partições de equivalência (PE) sobre o token
e o perfil, e análise de valores-limite (AVL) sobre a expiração do token.

Suíte v2: cópia da v1 revisada pela equipe. Mudanças em relação à v1 estão comentadas com "v2:".
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token
from tests.conftest import auth_header

ASSETS_URL = "/api/assets/"
ME_URL = "/api/auth/me"
MENSAGEM_SESSAO = "Sessão inválida ou expirada. Faça login novamente."

NOVO_ATIVO = {
    "title": "Dispositivo de teste",
    "asset_type": "Patente",
    "process_number": "BR 10 2025 123456-7",
    "deposit_date": "2025-01-10",
    "status": "Depositado",
    "authors": "Pessoa Autora",
}


def _token(payload: dict, secret: str | None = None) -> dict[str, str]:
    token = jwt.encode(payload, secret or settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}


# US02 / CA02-2 — critério de aceitação: autor vê apenas os ativos vinculados a ele
def test_autor_lista_somente_os_proprios_ativos(client: TestClient, assets) -> None:
    response = client.get(ASSETS_URL, headers=auth_header(client, "autora@teste.edu.br"))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Patente da autora"
    assert all(item["author_email"] == "autora@teste.edu.br" for item in body)


# US02 / CA02-2 — PE: outro autor também só vê o que é dele
def test_outro_autor_nao_ve_ativos_da_autora(client: TestClient, assets) -> None:
    response = client.get(ASSETS_URL, headers=auth_header(client, "outro@teste.edu.br"))

    titulos = [item["title"] for item in response.json()]
    assert titulos == ["Software de outro autor"]
    assert "Patente da autora" not in titulos


# US02 / CA02-3 — PE: autor sem nenhum ativo vinculado recebe lista vazia
def test_autor_sem_ativos_recebe_lista_vazia(client: TestClient, users) -> None:
    response = client.get(ASSETS_URL, headers=auth_header(client, "autora@teste.edu.br"))

    assert response.status_code == 200
    assert response.json() == []


# US03 / CA03-1 — PE inválida (perfil AUTOR) para a ação de cadastro
def test_autor_nao_pode_cadastrar_ativo(client: TestClient, users) -> None:
    response = client.post(ASSETS_URL, json=NOVO_ATIVO, headers=auth_header(client, "autora@teste.edu.br"))

    assert response.status_code == 403
    assert response.json()["detail"] == "Seu perfil não tem permissão para esta ação."


# US03 / CA03-1 — PE válida (perfil NIT) para a mesma ação, como contraste
def test_nit_pode_cadastrar_ativo(client: TestClient, users) -> None:
    response = client.post(ASSETS_URL, json=NOVO_ATIVO, headers=auth_header(client, "nit@teste.edu.br"))

    assert response.status_code == 201


# US03 / CA03-2 — PE inválida: requisições sem token em todas as rotas protegidas
@pytest.mark.parametrize(
    ("method", "url"),
    [("get", ASSETS_URL), ("post", ASSETS_URL), ("get", ME_URL)],
)
def test_rotas_protegidas_sem_token_retornam_401(client: TestClient, users, method: str, url: str) -> None:
    kwargs = {"json": NOVO_ATIVO} if method == "post" else {}
    response = getattr(client, method)(url, **kwargs)

    assert response.status_code == 401


# US03 / CA03-3 — PE inválida: token malformado
def test_token_malformado_retorna_401(client: TestClient, users) -> None:
    response = client.get(ME_URL, headers={"Authorization": "Bearer isto-nao-e-um-jwt"})

    assert response.status_code == 401
    assert response.json()["detail"] == MENSAGEM_SESSAO


# US03 / CA03-3 — PE inválida: token assinado com outra chave
def test_token_assinado_com_outra_chave_retorna_401(client: TestClient, users) -> None:
    exp = datetime.now(UTC) + timedelta(minutes=5)
    headers = _token({"sub": str(users["nit"].id), "exp": exp}, secret="chave-de-um-atacante")

    response = client.get(ME_URL, headers=headers)

    assert response.status_code == 401


# US03 / CA03-3 — valor-limite: token que expirou há 1 segundo
def test_token_expirado_retorna_401(client: TestClient, users) -> None:
    exp = datetime.now(UTC) - timedelta(seconds=1)
    response = client.get(ME_URL, headers=_token({"sub": str(users["nit"].id), "exp": exp}))

    assert response.status_code == 401
    assert response.json()["detail"] == MENSAGEM_SESSAO


# US03 / CA03-3 — valor-limite: token que ainda vale por mais alguns segundos
def test_token_prestes_a_expirar_ainda_e_aceito(client: TestClient, users) -> None:
    exp = datetime.now(UTC) + timedelta(seconds=30)
    response = client.get(ME_URL, headers=_token({"sub": str(users["nit"].id), "exp": exp}))

    assert response.status_code == 200


# US03 / CA03-4 — PE inválida: sub não numérico
def test_token_com_sub_nao_numerico_retorna_401(client: TestClient, users) -> None:
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {create_access_token('abc')}"})

    assert response.status_code == 401


# US03 / CA03-4 — PE inválida: token sem a claim sub
def test_token_sem_sub_retorna_401(client: TestClient, users) -> None:
    exp = datetime.now(UTC) + timedelta(minutes=5)
    response = client.get(ME_URL, headers=_token({"exp": exp}))

    assert response.status_code == 401


# US03 / CA03-4 — PE inválida: usuário do token não existe
def test_token_de_usuario_inexistente_retorna_401(client: TestClient, users) -> None:
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {create_access_token(99999)}"})

    assert response.status_code == 401


# US03 / CA03-5 — critério de aceitação: /me devolve o dono do token
@pytest.mark.parametrize(("email", "role"), [("nit@teste.edu.br", "NIT"), ("autora@teste.edu.br", "AUTOR")])
def test_me_retorna_dados_do_usuario_logado(client: TestClient, users, email: str, role: str) -> None:
    response = client.get(ME_URL, headers=auth_header(client, email))

    assert response.status_code == 200
    assert response.json()["email"] == email
    assert response.json()["role"] == role
