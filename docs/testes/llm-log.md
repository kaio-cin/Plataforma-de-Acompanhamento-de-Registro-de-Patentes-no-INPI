# Log de interação com a LLM — Sprint 3 (Parte 1)

## Identificação

| Item | Valor |
|---|---|
| LLM | Claude (Anthropic) |
| Modelo / versão | Claude Opus 5.5 — identificador de API `claude-opus-5-5` |
| Interface | claude.ai (sessão de agente com acesso ao repositório) |
| Data de uso | 13/11/2026 |
| Framework de teste pedido | pytest + `TestClient` do FastAPI (fixtures do `tests/conftest.py`) |
| Contexto fornecido | user stories US01, US02, US03, US04, US06, US07 com os critérios de aceitação; código de `core/`, `models/`, `schemas/`, `services/`, `routes/`, `main.py`, `tests/conftest.py`, `pyproject.toml` e `requirements-dev.txt` |
| Contexto **não** fornecido | partições, valores-limite e casos de teste da matriz (Etapa 1) |

**Ameaça à validade (registrada de propósito).** A mesma família de modelo que gerou a v1 também ajudou a equipe a
redigir a matriz da Etapa 1 numa sessão anterior. O prompt da v1 não continha a matriz, mas não dá para garantir que a
geração tenha sido completamente "cega". Para uma comparação totalmente independente, basta colar o prompt de
`prompts/v1-rodada-1.md` numa conversa nova (de qualquer LLM) e comparar a saída com `tests/v1-llm/`.

## Rodadas da v1 (sem edição manual)

O protocolo permite até 3 rodadas, apenas para a suíte compilar e rodar. Foi necessária **1 rodada**: a resposta já
carregou e executou sem nenhum ajuste.

| Rodada | Prompt (texto completo) | Resumo da resposta | Problemas observados |
|---|---|---|---|
| 1 | Arquivo [`prompts/v1-rodada-1.md`](prompts/v1-rodada-1.md) (31.891 caracteres: instruções + user stories com CAs + código do sistema). O trecho de instruções está reproduzido logo abaixo. | Três arquivos: `test_v1_autenticacao.py` (13 funções), `test_v1_perfis_sessao.py` (14 funções) e `test_v1_ativos.py` (28 funções). 55 funções de teste que, com `@pytest.mark.parametrize`, viram **92 casos**. Cada teste traz comentário `# USxx / CAxx-y — técnica`. Usa só bibliotecas já presentes (pytest, fastapi, python-jose). | Nenhum erro de import, de sintaxe ou de fixture. **0 testes sem compilar.** Execução: **91 passam, 1 falha** (`test_titulo_com_menos_de_3_caracteres_efetivos_retorna_422`). A falha foi investigada e é **defeito real do sistema** (BUG-01), não erro do teste. Lacunas vistas na inspeção: nenhum teste com campo **só de espaços** (título, processo, situação, autores), nenhum teste de **empate** na ordenação, e o teste de campos da listagem só confere a presença das chaves. |

### Instruções enviadas na rodada 1 (parte textual do prompt)

```text
Você é um engenheiro de testes experiente em Python. Preciso de uma suíte de testes automatizados para a API
back-end de um sistema de acompanhamento de patentes e programas de computador no INPI.

## Stack e framework de teste
- Python 3.13, FastAPI 0.143, SQLAlchemy 2.1, Pydantic 2, python-jose (JWT), passlib/bcrypt.
- Testes com pytest e o TestClient do FastAPI. Já existe um tests/conftest.py (abaixo) com fixtures de banco SQLite
  em memória, cliente HTTP, usuários e ativos de exemplo, e o helper auth_header. Use essas fixtures; não crie banco
  real nem dependa de rede.
- Os arquivos de teste serão colocados em uma subpasta de backend/tests/, e o pytest roda a partir de backend/
  (pythonpath = ["."]).

## User stories e critérios de aceitação
[US01, US02, US03, US04, US06, US07 com os 33 critérios CA01-1 … CA07-6 — texto completo no arquivo do prompt]

## O que eu quero
1. Gere a suíte de testes cobrindo todos os critérios de aceitação acima.
2. Aplique explicitamente partições de equivalência (classes válidas e inválidas de cada entrada), análise de
   valores-limite (os dois lados de cada fronteira) e cobertura dos critérios de aceitação.
3. Em cada teste, coloque um comentário indicando qual técnica ele aplica (partição, valor-limite ou critério de
   aceitação) e qual requisito/critério (ex.: # US04 / CA04-3 — valor-limite: título com 500 caracteres).
4. O resultado esperado de cada teste deve vir do critério de aceitação.
5. Entregue código completo, pronto para rodar com pytest, organizado em arquivos por assunto (autenticação,
   perfis/sessão, ativos).

## Código do sistema
[conteúdo integral de 17 arquivos — ver prompts/v1-rodada-1.md]
```

### Execução da v1

```text
$ cd backend
$ pytest tests/v1-llm --cov --cov-report=term-missing
FAILED tests/v1-llm/test_v1_ativos.py::test_titulo_com_menos_de_3_caracteres_efetivos_retorna_422
  fastapi.exceptions.ResponseValidationError: {'type': 'string_too_short', 'loc': ('response', 'title'),
  'msg': 'String should have at least 3 characters', 'input': 'ab'}
1 failed, 91 passed
```

### Investigação da falha

| Teste | Falha do teste ou do sistema? | Evidência |
|---|---|---|
| `test_titulo_com_menos_de_3_caracteres_efetivos_retorna_422` (título `" ab "`) | **Sistema (defeito real, BUG-01)** | O oráculo (422) vem do CA04-3 ("3 a 500 caracteres efetivos"). O Pydantic checa `min_length` **antes** do validador que remove os espaços, então `" ab "` (4 caracteres brutos) passa, é gravado como `"ab"`, e só a validação da **resposta** percebe o problema: a API devolve 500 com o registro já gravado. Reproduzido fora da suíte: depois disso, `GET /api/assets/` também passa a devolver 500 para o NIT. Registrado em [`defeitos.md`](defeitos.md). |

## Rodadas da v2

Ver a seção "Rodadas da v2" mais abaixo (preenchida na Etapa 4).
