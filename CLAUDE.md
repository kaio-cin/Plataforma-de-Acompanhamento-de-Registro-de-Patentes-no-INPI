# Radar INPI: contexto para o Claude Code

Leia este arquivo antes de qualquer tarefa. A divisão completa do trabalho está em `docs/divisao-tarefas.md`.

## O que é o projeto

Sistema web para o NIT (Núcleo de Inovação Tecnológica) acompanhar **patentes e programas de computador** no INPI. Hoje isso é manual: alguém lê a Revista da Propriedade Industrial (RPI, publicada toda terça) e procura os processos da instituição. O sistema baixa a RPI, cruza os despachos com os processos cadastrados e avisa a equipe antes de um prazo se perder.

Projeto da disciplina de Desenvolvimento de Software. **Apresentação final (Sprint 4): 07/12/2026.** Congelamento do código: 06/12.

Perfis de usuário:
- **NIT**: vê toda a carteira, cadastra e edita ativos.
- **AUTOR**: vê apenas os ativos vinculados a ele.

Os usuários não são técnicos: a interface deve ser clara e simples.

## Stack e estrutura

- `backend/`: Python, FastAPI, SQLAlchemy 2, SQLite (PostgreSQL depois), autenticação JWT (expira em 8 horas).
- `frontend/`: React 19, Vite, Tailwind 4, React Router.

Back-end em camadas. Um pedido passa por: `routes/` (recebe) → `schemas/` (valida o formato) → `services/` (regra de negócio) → `models/` (banco).

```
backend/app/{core,database,models,schemas,services,routes}  + main.py, seed.py
backend/tests/                  testes pytest
frontend/src/{pages,layouts,components,components/ui,api,context,hooks,utils}
frontend/src/index.css          cores e tokens visuais
frontend/e2e/                   testes Playwright
docs/qualidade/divida-tecnica.md  dívida técnica conhecida (DT-01 a DT-13)
```

## Como rodar

Back-end (pasta `backend`, com o ambiente `.venv` ativo):

```
python -m pip install -r requirements-dev.txt
copy .env.example .env          (macOS/Linux: cp)
python -m app.seed              (python -m app.seed --reset recomeça do zero)
python -m app.seed_codes        (só os códigos de despacho, sem usuários de teste; serve para produção)
python -m app.create_user --email E-MAIL --perfil NIT   (cria um usuário real; a senha é pedida no terminal)
uvicorn app.main:app --reload   (API em http://localhost:8000/docs)
pytest
```

Front-end (pasta `frontend`):

```
npm install
npm run dev                     (http://localhost:5173)
npm test
npm run test:e2e                (primeira vez: npx playwright install chromium)
```

Usuários de teste (só desenvolvimento): `nit@instituicao.edu.br` / `nit12345` e `fernanda.costa@instituicao.edu.br` / `autor12345`.

## Regras de código

- Textos da interface, mensagens de erro, docstrings e comentários em **português**, como no código existente.
- Regra de negócio fica em `services/`. As rotas só traduzem exceções de domínio em respostas HTTP. Os services não importam schemas HTTP (DT-05).
- Antes de criar um model, veja `models/columns.py`, `models/limits.py` e os models existentes e siga o mesmo padrão.
- Toda mudança de back-end vem com teste em `backend/tests/`. Rode `pytest` depois de alterar.
- Mudança de front-end: rode `npm test` e mantenha as cores nos tokens de `index.css`.
- Nunca leia, altere nem commite `.env`, arquivos `*.db` ou segredos.
- Leia os arquivos vizinhos antes de escrever, para seguir o padrão. Faça só o que foi pedido.

## Git

- Nunca trabalhe direto na `main`. Uma branch por tarefa, nome `tipo/assunto`: `feat/rpi-parser`, `feat/alertas-email`, `test/e2e-fluxo`, `chore/deploy`.
- Antes de começar: `git pull origin main`.
- Commits pequenos, de um assunto só, no formato `tipo(escopo): descrição curta`. Tipos: `feat`, `fix`, `test`, `docs`, `chore`. Exemplo: `feat(email): configuração SMTP no .env`.
- **Não rode `git commit`, `git push` nem abra Pull Request, a menos que o usuário peça.** Quando for útil, sugira a mensagem de commit.
- **Não adicione** `Co-Authored-By` nem "Generated with Claude Code" em commits ou descrições de PR.
- No GitHub o merge é feito com **"Create a merge commit"**, nunca com squash (squash apaga a contagem de commits de cada pessoa).
- Se a tarefa depende de um PR de outra pessoa que ainda não está na `main`, avise o usuário. Use `git fetch` e `git log origin/main` para conferir.
- Arquivos com mais risco de conflito: `models/__init__.py`, `main.py`, `App.jsx`, `Sidebar.jsx`, `seed.py`. Faça mudanças mínimas neles.

## Equipe e frentes

| Pessoa | Frente | US |
|---|---|---|
| Fred | Coleta e cruzamento da RPI | US08, US09, US10 |
| David | Alertas e e-mail | US11, US12, US13 |
| Guilherme | Editar ativo, linha do tempo, tela de edições da RPI | US05, US14, front da US10 |
| Kaio | Códigos de despacho, glossário, deploy, README | apoio à US11 |
| Breno | Qualidade, DT-13, teste de ponta a ponta, revisão de PRs | validação |

Não crie models, rotas ou telas que pertencem à frente de outra pessoa.

## Combinados entre as frentes

Models da RPI (Fred, devem entrar na `main` primeiro):
- `RpiEdition`: número, data, status (baixada, processada, erro), quantidade de despachos encontrados.
- `Dispatch`: ativo, edição, código, descrição, data de publicação, complemento.
- `DispatchCode`: código (seção 200 patentes, 700 programas), descrição, `exige_acao`, `prazo_dias`.

Model `Alert` (David): destinatário, despacho, ativo, tipo (informativo ou exige ação), prazo (publicação + `prazo_dias`), lido, e-mail enviado.

Função usada pela frente da RPI: `create_alerts_for(db, dispatch)`, no módulo de alertas (David). Cria um alerta para cada usuário NIT e para o autor vinculado ao ativo.

Formato JSON de `/timeline` e `/rpi/editions`: ainda a combinar. Registre aqui quando o grupo definir.

Alertas (US12, David). Cada usuário (NIT ou AUTOR) só vê e altera os próprios alertas; alerta de outro usuário ou inexistente responde 404.
- `GET /api/alerts/`: lista, do mais novo para o mais antigo, sem paginação. Filtros combináveis: `?unread=true` (só não lidos) e `?requires_action=true` (só os que exigem ação).
- `GET /api/alerts/unread-count`: `{"count": 3}`.
- `PATCH /api/alerts/{id}/read`: marca como lido e devolve o alerta (repetir não é erro).
- Campos de cada alerta: `id`, `asset_id`, `asset_title`, `process_number` (como cadastrado), `dispatch_code`, `dispatch_description`, `dispatch_plain_description` (explicação do glossário ou `null`), `publication_date`, `requires_action`, `deadline` (data ou `null`), `is_read`, `created_at`.

Glossário (Kaio). Qualquer usuário logado (NIT ou AUTOR) lê o glossário inteiro.
- `GET /api/dispatch-codes/`: lista sem paginação, patentes antes de programas e em ordem natural de código (`1.1`, `1.1.1`, `1.2`, `2.1`, `10.1`, `100`). Filtro opcional: `?asset_type=Patente` ou `?asset_type=Programa de Computador`.
- Campos de cada código: `id`, `code`, `asset_type`, `official_description`, `plain_description`, `requires_action`, `deadline_days` (dias corridos a partir da publicação, ou `null`).
