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

Na v2 a LLM foi usada de novo, agora com as lacunas encontradas na análise (Etapa 4). Cada teste sugerido foi revisado
contra o critério de aceitação antes de entrar em `tests/v2/`.

| Rodada | Prompt (texto completo) | Resumo da resposta | Problemas observados / revisão da equipe |
|---|---|---|---|
| 1 | Arquivo [`prompts/v2-rodada-1.md`](prompts/v2-rodada-1.md), reproduzido abaixo. Mesmo modelo (Claude Opus 5.5), mesma data. | `test_v2_lacunas.py` com 10 funções (14 casos), uma ou mais por lacuna G1…G6, cada uma com comentário `# Gx / USxx — CA — técnica`. | Revisão da equipe: (1) com o `client` padrão o BUG-01 aparece como **exceção** (`ResponseValidationError`), não como resposta; foi criado o fixture `api` com `raise_server_exceptions=False`, para o teste falhar na asserção (500 ≠ 422), como o usuário veria; (2) os 7 casos que esbarram no BUG-01 receberam `xfail(strict=True, raises=AssertionError)`: o oráculo continua sendo o do requisito, e a marcação passa a falhar assim que o defeito for corrigido; (3) a simulação da corrida (G5) troca `db_session.scalar` só durante o POST e desfaz com `monkeypatch.undo()` antes de conferir a listagem. Nenhum teste precisou de oráculo corrigido. |

```text
Continuando a suíte de testes que você gerou para a API do Radar INPI (pytest + TestClient, mesmas fixtures do
`tests/conftest.py` e o mesmo código enviado antes). Medimos a suíte e cruzamos com o nosso projeto manual de testes.
Encontramos as lacunas abaixo. Para **cada lacuna**, escreva testes específicos, com comentário indicando a lacuna
(G1…G6), o critério de aceitação e a técnica. O resultado esperado deve vir do critério de aceitação, nunca do
comportamento atual do código: se o código estiver errado, o teste deve falhar.

- **G1 — partição "somente espaços" não testada** (CA04-3, CA04-4, CA04-7, CA04-8). Título, número do processo,
  situação e autores compostos só de espaços (com tamanho bruto acima do mínimo) devem ser recusados com 422.
- **G2 — valor-limite do título efetivo incompleto** (CA04-3). Vocês testaram `" ab "` (2 efetivos). Falta o outro
  lado da fronteira, `"  abc  "` (3 efetivos → 201, gravado `"abc"`), e o limite superior efetivo: 500 caracteres
  com espaços nas bordas devem ser aceitos.
- **G3 — empate na ordenação** (CA06-2). Dois ativos com a mesma data de depósito: o cadastrado por último deve vir
  primeiro. A ordem dos três ativos da fixture também deve ser conferida exatamente, não só "datas ordenadas".
- **G4 — asserção fraca na listagem** (CA06-3). O teste atual só confere se as chaves existem. Confira os
  **valores** de cada item contra o que foi gravado (inclusive `author_email` nulo para o ativo sem autor).
- **G5 — linhas 49–52 de `asset_service.create_asset` não cobertas** (CA04-5). É o `except IntegrityError` que trata
  duas requisições simultâneas com o mesmo processo. Simule a corrida sem threads e confira 409 e que nada foi
  duplicado.
- **G6 — oráculo acoplado à implementação** (CA01-1). `test_token_emitido_contem_sub_e_role` decodifica o JWT e
  confere `sub == id` e a presença de `exp`. O critério só diz que o token identifica o usuário e o perfil: reescreva
  verificando o comportamento (o token é aceito por `/auth/me` e devolve o mesmo usuário).

Além disso: um cadastro inválido não pode deixar a carteira indisponível. Depois de uma tentativa com título só de
espaços, `GET /api/assets/` do NIT deve continuar respondendo 200 (CA06-1).
```

Ajustes nos arquivos copiados da v1 (feitos pela equipe, sem LLM):

- `test_token_emitido_contem_sub_e_role` saiu; quem cobre o CA01-1 agora é o teste da lacuna G6.
- `test_titulo_com_menos_de_3_caracteres_efetivos_retorna_422` foi para `test_v2_lacunas.py` (L13 completo, G2).
- `test_itens_da_listagem_trazem_campos_esperados` (asserção fraca) foi substituído pelo teste da lacuna G4.

### Execução da v2

```text
$ cd backend
$ pytest tests/v2 --cov --cov-report=term-missing
96 passed, 7 xfailed
TOTAL  196 stmts  0 miss  26 branches  0 partial  100%
```
