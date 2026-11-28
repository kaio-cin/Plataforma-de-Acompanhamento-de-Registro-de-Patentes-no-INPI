# Radar INPI

Sistema web para o NIT (Núcleo de Inovação Tecnológica) acompanhar os **pedidos de patente e os registros de programa de computador** da instituição no INPI.

Hoje esse acompanhamento é manual: toda terça-feira alguém lê a Revista da Propriedade Industrial (RPI) procurando os processos da instituição. O Radar INPI baixa a RPI, cruza os despachos com os processos cadastrados e avisa a equipe antes que um prazo se perca.

Projeto da disciplina de Desenvolvimento de Software (UFCA).

## Quem usa

| Perfil | O que vê e faz |
|---|---|
| **NIT** | Toda a carteira de ativos. Cadastra e edita ativos, acompanha as edições da RPI e recebe todos os alertas. |
| **Autor** (inventor ou desenvolvedor) | Só os ativos vinculados a ele e os alertas desses ativos. |

Os dois perfis acessam o glossário de despachos, que explica em linguagem simples o que cada código publicado pelo INPI significa.

## Funcionalidades

| Funcionalidade | Histórias | Situação em 28/11/2026 |
|---|---|---|
| Login e perfis | US01, US02, US03 | Pronto |
| Cadastro e carteira de ativos | US04, US06, US07 | Pronto |
| Edição de ativo | US05 | Em desenvolvimento |
| Coleta da RPI | US08 | Download e leitura do XML prontos; agendamento semanal e botão "Processar agora" em desenvolvimento |
| Cruzamento com os ativos | US09 | Pronto no back-end: grava os despachos, liga ao glossário e cria os alertas. Falta a rota que dispara o processamento |
| Edições da RPI processadas | US10 | Em desenvolvimento |
| Alertas por e-mail | US11 | Envio pronto; falta disparar os e-mails depois de cada processamento da RPI |
| Alertas no painel | US12 | Pronto: tela com filtros, prazo em destaque, "marcar como lido" e contador na barra superior |
| Alerta para o autor vinculado | US13 | Pronto |
| Linha do tempo do ativo | US14 | Em desenvolvimento |
| Glossário de despachos | apoio à US11 | Pronto: 361 códigos oficiais do INPI e tela para os dois perfis |
| Banco PostgreSQL para a publicação | — | Pronto; publicação do sistema em preparação |

A divisão do trabalho e o cronograma estão em [`docs/divisao-tarefas.md`](docs/divisao-tarefas.md).

## Tecnologias

- **Back-end:** Python, FastAPI, SQLAlchemy 2, SQLite (PostgreSQL na publicação) e autenticação JWT.
- **Front-end:** React 19, Vite, Tailwind CSS 4 e React Router.
- **Testes:** pytest (back-end), Vitest (front-end) e Playwright (ponta a ponta).

## Como rodar

Versões usadas no desenvolvimento e nos testes: Python 3.14 e Node.js 24. O back-end usa recursos do Python 3.11, então versões anteriores não funcionam.

### Back-end

Na pasta `backend`:

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
python -m app.seed                # dados de demonstração e códigos de despacho
uvicorn app.main:app --reload
```

A API fica em http://localhost:8000. A documentação interativa fica em http://localhost:8000/docs.

### Front-end

Na pasta `frontend`, com o back-end rodando:

```bash
npm install
npm run dev
```

O sistema abre em http://localhost:5173.

### Usuários de demonstração

Criados por `python -m app.seed`, **só para desenvolvimento**:

| Perfil | E-mail | Senha |
|---|---|---|
| NIT | `nit@instituicao.edu.br` | `nit12345` |
| Autor | `fernanda.costa@instituicao.edu.br` | `autor12345` |

### Comandos de dados

| Comando (pasta `backend`) | O que faz |
|---|---|
| `python -m app.seed` | Cria usuários e ativos de demonstração e carrega os códigos de despacho. Não apaga nada. |
| `python -m app.seed --reset` | Apaga **todos** os dados e recomeça com os de demonstração. |
| `python -m app.seed_codes` | Carrega só os códigos de despacho do INPI. Não cria usuários; é o comando para produção. |

## Configuração

O back-end lê as configurações de variáveis de ambiente ou do arquivo `backend/.env`. O modelo é o [`backend/.env.example`](backend/.env.example).

| Variável | Para que serve |
|---|---|
| `DATABASE_URL` | Banco de dados. O padrão é SQLite (`sqlite:///./pi_inpi.db`). |
| `JWT_SECRET_KEY` | Chave que assina os logins. **Troque em produção** por um valor longo e aleatório. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duração do login (padrão: 480 minutos, 8 horas). |
| `CORS_ORIGINS` | Endereços do front-end autorizados a chamar a API, separados por vírgula. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` | Envio dos alertas por e-mail. Com `SMTP_HOST` vazio, o e-mail só é mostrado no terminal. |

No front-end, `VITE_API_URL` aponta para a API (padrão: `http://localhost:8000/api`).

## Testes

```bash
# pasta backend
pytest

# pasta frontend
npm test                          # testes unitários
npm run test:e2e                  # ponta a ponta; na primeira vez: npx playwright install chromium
```

Os testes ponta a ponta sobem a API e o front-end em portas próprias, com um banco separado (`backend/e2e.db`), sem mexer nos dados de desenvolvimento.

## Estrutura

```
backend/
  app/
    routes/      recebe os pedidos HTTP
    schemas/     valida o formato dos dados
    services/    regras de negócio
    models/      tabelas do banco
    core/        configuração e segurança
    database/    conexão com o banco
  tests/         testes pytest
frontend/
  src/
    pages/       telas
    components/  componentes reutilizáveis
    api/         chamadas à API
    hooks/ context/ utils/ layouts/
  e2e/           testes Playwright
docs/            divisão de tarefas, glossário, qualidade e testes
```

Um pedido passa pelas camadas nesta ordem: `routes` → `schemas` → `services` → `models`. As regras de negócio ficam só em `services`.

## Documentação

- [`docs/divisao-tarefas.md`](docs/divisao-tarefas.md): o que falta, quem faz e o cronograma.
- [`docs/qualidade/divida-tecnica.md`](docs/qualidade/divida-tecnica.md): dívida técnica conhecida.
- [`docs/testes/matriz-rastreabilidade.md`](docs/testes/matriz-rastreabilidade.md): histórias de usuário e testes que as cobrem.
- [`docs/testes/defeitos.md`](docs/testes/defeitos.md): defeitos encontrados.
- [`CLAUDE.md`](CLAUDE.md): regras de código, de Git e combinados entre as frentes.

## Como contribuir

- Uma branch por tarefa, no formato `tipo/assunto` (por exemplo, `feat/alertas-email`), sempre a partir da `main` atualizada.
- Commits pequenos, no formato `tipo(escopo): descrição curta`. Tipos: `feat`, `fix`, `test`, `docs`, `chore`.
- Toda mudança no back-end vem com teste. Antes do Pull Request, `pytest` e `npm test` precisam passar.
- O merge é feito com **"Create a merge commit"**, nunca com squash.

## Equipe

| Pessoa | Frente |
|---|---|
| Fred | Coleta e cruzamento da RPI |
| David | Alertas e e-mail |
| Guilherme | Edição de ativo, linha do tempo e tela de edições da RPI |
| Kaio | Códigos de despacho, glossário, publicação e documentação |
| Breno | Qualidade, testes ponta a ponta e revisão |
