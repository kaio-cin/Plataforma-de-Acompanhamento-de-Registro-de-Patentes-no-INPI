"""Testes de autenticação — US01 (login NIT) e US02 (login autor).

Técnicas aplicadas: critérios de aceitação (CA), partições de equivalência (PE)
e análise de valores-limite (AVL).
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import decode_access_token
from tests.conftest import PASSWORD

LOGIN_URL = "/api/auth/login"
TOKEN_URL = "/api/auth/token"
MENSAGEM_CREDENCIAIS = "E-mail ou senha incorretos."


# US01 / CA01-1 — critério de aceitação + PE (e-mail NIT válido, senha correta)
def test_login_nit_com_credenciais_corretas_retorna_token_e_perfil(client: TestClient, users) -> None:
    response = client.post(LOGIN_URL, json={"email": "nit@teste.edu.br", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "nit@teste.edu.br"
    assert body["user"]["role"] == "NIT"


# US01 / CA01-1 — critério de aceitação: o token emitido identifica o usuário e o perfil
def test_token_emitido_contem_sub_e_role(client: TestClient, users) -> None:
    response = client.post(LOGIN_URL, json={"email": "nit@teste.edu.br", "password": PASSWORD})

    payload = decode_access_token(response.json()["access_token"])
    assert payload is not None
    assert payload["sub"] == str(users["nit"].id)
    assert payload["role"] == "NIT"
    assert "exp" in payload


# US01 / CA01-2 — PE inválida: senha incorreta para e-mail existente
def test_login_com_senha_incorreta_retorna_401(client: TestClient, users) -> None:
    response = client.post(LOGIN_URL, json={"email": "nit@teste.edu.br", "password": "senha-errada"})

    assert response.status_code == 401
    assert response.json()["detail"] == MENSAGEM_CREDENCIAIS


# US01 / CA01-3 — PE inválida: e-mail com formato válido mas não cadastrado
def test_login_com_email_inexistente_retorna_mesma_mensagem(client: TestClient, users) -> None:
    response = client.post(LOGIN_URL, json={"email": "naoexiste@teste.edu.br", "password": PASSWORD})

    assert response.status_code == 401
    assert response.json()["detail"] == MENSAGEM_CREDENCIAIS


# US01 / CA01-2 e CA01-3 — critério de aceitação: as duas falhas são indistinguíveis
def test_mensagens_de_erro_de_login_sao_identicas(client: TestClient, users) -> None:
    senha_errada = client.post(LOGIN_URL, json={"email": "nit@teste.edu.br", "password": "x1"})
    email_errado = client.post(LOGIN_URL, json={"email": "ninguem@teste.edu.br", "password": "x1"})

    assert senha_errada.status_code == email_errado.status_code == 401
    assert senha_errada.json() == email_errado.json()


# US01 / CA01-4 — PE válida: e-mail cadastrado com variação de maiúsculas
@pytest.mark.parametrize("email", ["NIT@teste.edu.br", "Nit@Teste.Edu.Br", "NIT@TESTE.EDU.BR"])
def test_login_ignora_maiusculas_no_email(client: TestClient, users, email: str) -> None:
    response = client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "nit@teste.edu.br"


# US01 / CA01-5 — PE inválida: formato de e-mail inválido
@pytest.mark.parametrize("email", ["nao-e-email", "sem-arroba.com", "@teste.edu.br", ""])
def test_login_com_email_malformado_retorna_422(client: TestClient, users, email: str) -> None:
    response = client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})

    assert response.status_code == 422


# US01 / CA01-5 — valor-limite: senha com 0 caracteres (abaixo do mínimo 1)
def test_login_com_senha_vazia_retorna_422(client: TestClient, users) -> None:
    response = client.post(LOGIN_URL, json={"email": "nit@teste.edu.br", "password": ""})

    assert response.status_code == 422


# US01 / CA01-5 — valor-limite: senha com 1 caractere (no mínimo) passa na validação e cai no 401
def test_login_com_senha_de_um_caractere_passa_validacao(client: TestClient, users) -> None:
    response = client.post(LOGIN_URL, json={"email": "nit@teste.edu.br", "password": "a"})

    assert response.status_code == 401


# US01 / CA01-5 — PE inválida: campos obrigatórios ausentes
@pytest.mark.parametrize("payload", [{"email": "nit@teste.edu.br"}, {"password": PASSWORD}, {}])
def test_login_sem_campos_obrigatorios_retorna_422(client: TestClient, users, payload: dict) -> None:
    response = client.post(LOGIN_URL, json=payload)

    assert response.status_code == 422


# US01 / CA01-6 — critério de aceitação: formulário OAuth2 equivalente ao login JSON
def test_login_via_formulario_oauth2_com_credenciais_corretas(client: TestClient, users) -> None:
    response = client.post(TOKEN_URL, data={"username": "nit@teste.edu.br", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "NIT"
    assert response.json()["token_type"] == "bearer"


# US01 / CA01-6 — PE inválida no formulário OAuth2: senha incorreta
def test_login_via_formulario_oauth2_com_senha_errada_retorna_401(client: TestClient, users) -> None:
    response = client.post(TOKEN_URL, data={"username": "nit@teste.edu.br", "password": "errada"})

    assert response.status_code == 401
    assert response.json()["detail"] == MENSAGEM_CREDENCIAIS


# US02 / CA02-1 — critério de aceitação + PE (e-mail de AUTOR cadastrado)
def test_login_autor_retorna_perfil_autor(client: TestClient, users) -> None:
    response = client.post(LOGIN_URL, json={"email": "autora@teste.edu.br", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "AUTOR"
    assert decode_access_token(body["access_token"])["role"] == "AUTOR"
