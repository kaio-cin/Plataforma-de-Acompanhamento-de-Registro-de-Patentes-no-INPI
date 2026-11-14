# Log de análise de qualidade — Sprint 3 (Parte 2)

Registro de **onde** procuramos, **com o quê** e **o que foi descartado**. Cada item aceito foi confirmado por
leitura do código antes de entrar em [`divida-tecnica.md`](divida-tecnica.md).

## 1. Escopo

| Incluído | Motivo | Fora do escopo | Motivo |
|---|---|---|---|
| `backend/app/services/` | Regras de negócio (cadastro, visibilidade por perfil, autenticação) | `frontend/` | Parte 2 foca no back-end, mesmo escopo da suíte de testes da Parte 1 (rede de proteção) |
| `backend/app/routes/` | Tradução HTTP ↔ regra, controle de perfil | `app/routes/health.py` | 1 função, sem regra |
| `backend/app/schemas/`, `backend/app/models/` | Regras de validação e de persistência | `tests/` | Código de teste não entra no relatório de dívida |
| `backend/app/core/`, `database/`, `main.py`, `seed.py` | Configuração e infraestrutura que as regras usam | | |

Ordem da leitura guiada (tabelas de propriedades, SOLID e smells do enunciado): services → routes → schemas/models →
core/database/main/seed. Para cada módulo: responsabilidade clara? Expõe detalhes internos? De quantos módulos
depende? Que smells aparecem?

## 2. Ferramentas (Python: equivalentes às sugeridas para JS/TS)

| Ferramenta | Equivale a | Configuração | Saída |
|---|---|---|---|
| Ruff 0.17.5 (regras `C90`, `PLR0911–0915`, `PLR2004`, `SIM`, `ARG`, `RET`, `PIE`) | ESLint `complexity`, `max-params`, `no-magic-numbers` | `max-complexity = 5`, `max-args = 4` | [`ferramentas/ruff.txt`](ferramentas/ruff.txt) |
| Ruff `--select ALL` (sem regras de documentação/estilo) | eslint-plugin-sonarjs | ver cabeçalho do arquivo | [`ferramentas/ruff.txt`](ferramentas/ruff.txt) |
| Radon 6 (`cc -s -a`, `mi -s`) | complexidade ciclomática / índice de manutenibilidade | padrão | [`radon_cc.txt`](ferramentas/radon_cc.txt), [`radon_mi.txt`](ferramentas/radon_mi.txt) |
| Pylint 4 `duplicate-code` | jscpd (intra-linguagem) | `--min-similarity-lines=3 --ignore-imports=yes` | [`pylint_dup.txt`](ferramentas/pylint_dup.txt) |
| jscpd 4 (`--format python`) | jscpd | `--min-tokens 20 --min-lines 3` | [`jscpd.txt`](ferramentas/jscpd.txt) |
| Script de acoplamento (AST) | madge / dependency-cruiser | [`ferramentas/acoplamento.py`](ferramentas/acoplamento.py) | [`acoplamento.txt`](ferramentas/acoplamento.txt) |

### O que as ferramentas apontaram

| Ferramenta | Achado | Decisão |
|---|---|---|
| Ruff (regras de smell) | **Nenhum** aviso com `max-complexity = 5` e `max-args = 4`. `PLR2004` só pega números mágicos em **comparações**; os limites `500`, `50`, `100`, `1000` aparecem como argumentos (`String(500)`, `max_length=500`) e passaram despercebidos. | Registrado como limitação; o problema virou DT-01 pela leitura manual |
| Ruff `DTZ011` | `date.today()` em `schemas/asset.py:48` | **Aceito** → DT-10 |
| Ruff `PLC0415` | `import app.models` dentro de `init_db()` e `reset_db()` | Descartado: o import tardio é de propósito (registra os models no metadata sem ciclo de import) |
| Ruff `UP042` | `class UserRole(str, Enum)` → `StrEnum` | Descartado: estilo, sem efeito no projeto |
| Ruff `FAST001` | `response_model` redundante em `routes/auth.py` | Descartado: estilo |
| Ruff `TC003` | mover `datetime.date` para `TYPE_CHECKING` em `models/asset.py` | **Falso positivo**: o SQLAlchemy resolve `Mapped[date]` em tempo de execução; mover o import quebra o mapeamento |
| Radon CC | `seed()` = B (8), `create_asset()` = B (6); todo o resto A | `seed` → contribui para DT-11; `create_asset` não é Long Method (ver LLM, A1) |
| Radon MI | todos os módulos A (61–100) | Nada a registrar |
| Pylint `duplicate-code` | Nenhuma duplicação | Limitação: só pega linhas idênticas |
| jscpd | 2 clones entre `models/asset.py` e `models/user.py`: bloco de imports (3 linhas) e configuração do `SAEnum` (4 linhas) | Imports: descartado (inevitável). `SAEnum`: **aceito** → DT-02 |
| Script de acoplamento | `services.asset_service` depende de `schemas.asset` (camada HTTP) e de `services.auth_service`; `core.config` tem 4 dependentes diretos; `routes.*` com Ce = 4 | **Aceito** → DT-05, DT-06, DT-12 |

## 3. LLM

Modelo: Claude Opus 5.5 (`claude-opus-5-5`), claude.ai, 13/11/2026. Um módulo (ou grupo pequeno) por prompt, sempre
pedindo o trecho. Modelo de prompt (o `<código>` foi substituído pelo conteúdo integral dos arquivos listados):

```text
Analise o código Python abaixo (back-end FastAPI + SQLAlchemy de um sistema de acompanhamento de patentes no INPI).
Aponte, com o trecho exato (arquivo e linhas) e uma justificativa curta:
1) violações de propriedades de projeto: integridade conceitual, information hiding, coesão, acoplamento;
2) violações dos princípios SOLID (SRP, OCP, LSP, ISP, DIP);
3) code smells (Long Method, Large Class, Duplicated Code, Feature Envy, Long Parameter List, Switch Statements,
   Magic Numbers e outros que encontrar).
Para cada achado, diga qual consequência concreta ele traz (o que fica difícil de mudar ou de testar).
Não sugira mudanças de comportamento; estamos procurando dívida técnica.

Arquivos: <lista>
<código>
```

| Prompt | Arquivos enviados | Achados da LLM | Revisão da equipe |
|---|---|---|---|
| A | `services/asset_service.py`, `services/auth_service.py` | A1 `create_asset` é Long Method e viola SRP (checa duplicidade, resolve autor, monta, grava, trata corrida). A2 o service depende de `AssetCreate` (schema HTTP) e de `Session` (DIP). A3 mensagem de processo duplicado repetida. A4 `authenticate` sinaliza falha com `None` enquanto `asset_service` lança exceções. A5 `_DUMMY_HASH` calculado no import é efeito colateral lento. A6 `asset_service` importa `get_user_by_email` de `auth_service` (Feature Envy / acoplamento entre services). A7 `if user.role != UserRole.NIT` decide a visibilidade (OCP). | A1 **falso positivo**: 20 linhas, CC 5, tudo é o mesmo caso de uso (cadastrar); dividir criaria funções de uma linha. A2 **aceito** (DT-05, DT-06). A3 **aceito** (DT-04). A4 **aceito** (DT-08). A5 **descartado**: é proposital (tempo constante contra enumeração de e-mails), documentado no comentário. A6 **aceito**, incorporado ao DT-06. A7 **aceito** (DT-07). |
| B | `routes/auth.py`, `routes/assets.py`, `routes/deps.py` | B1 `login` e `login_form` duplicados. B2 `_INVALID_CREDENTIALS` é uma **instância** de exceção global reutilizada. B3 `require_roles` devolve closure, o que violaria ISP. B4 `try/except` por tipo em `create_asset` é Switch Statement. B5 `"sub"` e `isdigit()` são literais mágicos. | B1 e B2 **aceitos** (DT-03). B3 **falso positivo**: ISP trata de interfaces com métodos que o cliente não usa; uma fábrica de dependência não é isso. B4 **descartado**: dois `except` explícitos são mais claros que polimorfismo neste tamanho; reavaliar quando a US05 trouxer mais erros. B5 **descartado**: `sub` é a claim padrão do JWT. |
| C | `schemas/asset.py`, `schemas/auth.py`, `models/*.py` | C1 limites de tamanho repetidos entre models e schemas. C2 configuração do `SAEnum` repetida. C3 `Asset.author_email` é propriedade de apresentação dentro do model ORM. C4 `UserRole(str, Enum)` viola LSP. C5 os validadores rodam depois das restrições de tamanho, então espaços burlam o mínimo. C6 `date.today()` é dependência oculta do relógio. C7 `AssetRead` é Large Class. | C1 **aceito** (DT-01). C2 **aceito** (DT-02, também visto pelo jscpd). C3 **aceito** (DT-09). C4 **falso positivo**: herdar de `str` é o jeito padrão de ter enum serializável; o objeto continua substituível por `str`. C5 **correto, mas é defeito, não dívida**: muda comportamento, já registrado como BUG-01 na Parte 1 (`docs/testes/defeitos.md`). C6 **aceito** (DT-10). C7 **falso positivo**: 4 linhas. |
| D | `core/config.py`, `core/security.py`, `database/session.py`, `main.py`, `seed.py` | D1 `settings` global importado direto (DIP, testabilidade). D2 `seed` repete as regras de cadastro em vez de usar o service. D3 segredo JWT padrão no código. D4 `engine` criado no import. D5 `if _is_sqlite` é Switch Statement sobre o banco. | D1 **aceito** (DT-12), D4 incorporado a ele. D2 **aceito** (DT-11). D3 **real, mas é segurança, não qualidade de projeto**: anotado para o backlog de segurança. D5 **falso positivo**: um único ponto de configuração. |

**Placar da LLM:** 24 achados → 14 aceitos (fundidos em 12 itens de dívida), 1 correto mas reclassificado como
defeito, 5 falsos positivos e 4 descartados por decisão de projeto ou por fugir do escopo.

## 4. Leitura manual

Além de confirmar cada achado acima, a leitura manual trouxe o que ferramentas e LLM não trouxeram:

- **DT-13 (só manual)**: `AssetRead` herda de `AssetBase`, então a **resposta** revalida as regras de **entrada**
  (`min_length`, `max_length`). Qualquer registro que não obedeça às regras de hoje (dado antigo, seed, regra que
  ficou mais rígida ou o próprio BUG-01) derruba `GET /api/assets/` inteiro com 500. É isso que transforma o BUG-01
  de "um cadastro ruim" em "carteira fora do ar".

- **DT-07**, consequência concreta: `list_assets_for` trata **qualquer** perfil que não seja NIT como autor. Um terceiro
  perfil cairia silenciosamente na visão de autor, sem erro.
- **DT-02**, consequência concreta: o comentário que explica a escolha `native_enum=False` + `values_callable` só
  existe em `user.py`. Quem copiar a configuração sem o `values_callable` (por exemplo, para o tipo de despacho da
  US09) grava o **nome** do membro e não o valor, e nenhum teste de API percebe (o enum volta igual na leitura).
- **Lacuna da rede de proteção**: a suíte da Parte 1 não cobre o formato do banco (DDL, valores gravados dos enums).
  Antes das refatorações DT-01 e DT-02, escrevemos `tests/test_esquema_banco.py` (testes de caracterização).
- **DT-01** ligado ao **BUG-01**: o mesmo número (por exemplo, 3 para o título) mora em dois lugares e é aplicado
  sobre o valor bruto, não sobre o normalizado.
