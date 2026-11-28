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
| Coleta da RPI | US08 | Pronto no back-end: download e leitura do XML, rota "Processar agora" (`POST /api/rpi/process`) e agendamento semanal (desligado por padrão no código; ligado na configuração do Render, no `render.yaml`). Falta o botão "Processar agora" na tela |
| Cruzamento com os ativos | US09 | Pronto: grava os despachos, liga ao glossário e cria os alertas. É disparado pela rota "Processar agora" e pelo agendamento |
| Edições da RPI processadas | US10 | Pronto no back-end (`GET /api/rpi/editions`, só NIT). Falta a tela de edições da RPI |
| Alertas por e-mail | US11 | Pronto: os e-mails saem depois de cada processamento manual que dá certo e no fim de cada execução do agendamento. O Render gratuito bloqueia as portas SMTP 25, 465 e 587 (ver "Publicação") |
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
| `python -m app.create_user --email E-MAIL --perfil NIT` | Cria um usuário (perfil `NIT` ou `AUTOR`). A senha é pedida duas vezes e não aparece na tela. |

## Configuração

O back-end lê as configurações de variáveis de ambiente ou do arquivo `backend/.env`. O modelo é o [`backend/.env.example`](backend/.env.example).

| Variável | Para que serve |
|---|---|
| `DATABASE_URL` | Banco de dados. O padrão é SQLite (`sqlite:///./pi_inpi.db`). |
| `JWT_SECRET_KEY` | Chave que assina os logins. **Troque em produção** por um valor longo e aleatório. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duração do login (padrão: 480 minutos, 8 horas). |
| `CORS_ORIGINS` | Endereços do front-end autorizados a chamar a API, separados por vírgula. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` | Envio dos alertas por e-mail. Com `SMTP_HOST` vazio, o e-mail só é mostrado no terminal, e o alerta conta como enviado. |
| `RPI_SCHEDULER_ENABLED` | Liga a coleta automática da RPI: terças e quartas às 9h, 13h e 18h (horário de Brasília), mais uma verificação cerca de 30 segundos depois que a API sobe. Padrão: `false` (desligada), inclusive no desenvolvimento local; deixe assim no seu computador. Na publicação, o `render.yaml` define `true` (veja "Coleta automática da RPI"). |

No front-end, `VITE_API_URL` aponta para a API (padrão: `http://localhost:8000/api`).

## Processar a RPI manualmente

Enquanto a tela de edições da RPI não fica pronta, o processamento é disparado pela documentação interativa da API, com um usuário do **NIT**. No computador, o endereço é http://localhost:8000/docs. Na publicação, é `https://ENDEREÇO-DA-API/docs`, mas o processamento no Render ainda não foi testado.

1. Abra o `/docs` e clique em **Authorize**, no alto da página.
2. Em `username`, informe o **e-mail** do usuário NIT e, em `password`, a senha. Deixe os outros campos em branco e clique em **Authorize**. Por padrão, o login vale 8 horas.
3. Abra **POST /api/rpi/process** e clique em **Try it out**.
4. O corpo do pedido pode vir preenchido com um valor de exemplo. Apague todo o conteúdo e escreva:
   - **sem número** (`{}`): processa a edição da terça-feira mais recente, pelo horário de Brasília;
   - **com número** (`{"number": 2916}`): processa a edição informada. Serve para repetir uma edição ou recuperar uma semana perdida.
5. Clique em **Execute**. O sistema baixa a RPI do site do INPI, cruza os despachos com os ativos cadastrados e cria os alertas. **Pode levar alguns minutos.**

A resposta mostra a edição e um resumo: despachos lidos, despachos que cruzaram com os ativos, despachos novos e alertas criados. Processar de novo a mesma edição não repete despachos nem alertas. Os e-mails dos alertas saem logo depois, só quando o processamento dá certo.

Para ver as edições já registradas, use **GET /api/rpi/editions** (da mais nova para a mais antiga).

| Resposta | O que significa |
|---|---|
| 401 | Sem login ou login expirado. Clique em **Authorize** de novo. |
| 403 | O usuário não é do NIT. |
| 404 | A edição ainda não foi publicada pelo INPI. |
| 409 | A edição já está sendo processada. Tente de novo em alguns minutos. |
| 422 | Número de edição inválido (precisa ser um número inteiro de 1 a 99999). |
| 502 | Não foi possível baixar a RPI ou o arquivo do INPI veio num formato que não pôde ser lido. |
| 500 | Falha ao cruzar a edição com os ativos ou ao gravar o resultado. Tente processar de novo. |

## Publicação

O back-end e o banco ficam no **Render**, e o front-end fica na **Vercel**. A publicação é para uso real: não há dados de demonstração nem senhas de teste. Os arquivos de configuração já estão no repositório: [`render.yaml`](render.yaml) e [`frontend/vercel.json`](frontend/vercel.json).

### Primeira publicação

1. **Back-end e banco no Render.** Em *New → Blueprint*, escolha este repositório. O Render lê o `render.yaml` e cria a API (`radar-inpi-api`) e o banco PostgreSQL (`radar-inpi-db`).
   - Quando ele pedir `CORS_ORIGINS`, informe o endereço que o front-end terá na Vercel (por exemplo, `https://radar-inpi.vercel.app`). Se ainda não souber, preencha depois no passo 3.
   - A `JWT_SECRET_KEY` é gerada pelo próprio Render, e a `DATABASE_URL` vem do banco.
   - O `render.yaml` também liga a coleta automática da RPI (`RPI_SCHEDULER_ENABLED=true`), com um único processo (`WEB_CONCURRENCY=1`). Antes de cadastrar os ativos, leia "Coleta automática da RPI".
   - A cada inicialização, a API carrega ou atualiza os códigos de despacho (`python -m app.seed_codes`).
   - Confira se a API responde em `https://ENDEREÇO-DA-API/api/health`.
2. **Front-end na Vercel.** Em *Add New → Project*, importe este repositório.
   - Em *Root Directory*, escolha `frontend`.
   - Em *Environment Variables*, crie `VITE_API_URL` com o endereço da API mais `/api` (por exemplo, `https://radar-inpi-api.onrender.com/api`).
   - O `vercel.json` faz endereços como `/glossario` funcionarem ao recarregar a página.
3. **Ligar um ao outro.** No Render, em *radar-inpi-api → Environment*, confira se `CORS_ORIGINS` tem exatamente o endereço do front-end na Vercel, sem barra no final.
4. **Criar o primeiro usuário do NIT.** O plano gratuito do Render não tem terminal, então o comando roda no seu computador, ligado ao banco publicado:
   - no Render, abra *radar-inpi-db → Connect* e copie a **External Database URL**;
   - na pasta `backend`, com o `.venv` ativo, rode:

   ```powershell
   $env:DATABASE_URL = "COLE-AQUI-A-EXTERNAL-DATABASE-URL"     # cmd: set DATABASE_URL=...
   python -m app.create_user --email coordenacao.nit@instituicao.edu.br --perfil NIT
   Remove-Item Env:DATABASE_URL                                # volta a usar o banco local
   ```

   O comando mostra o banco em uso (sem a senha) antes de pedir a senha do novo usuário. Do mesmo jeito se criam os autores (`--perfil AUTOR`). A External Database URL contém a senha do banco: não a coloque em arquivos do repositório nem em mensagens.

### Coleta automática da RPI

No código, a coleta automática vem desligada, e no desenvolvimento local ela continua assim. Na publicação, o `render.yaml` a liga com um único processo: `RPI_SCHEDULER_ENABLED=true` e `WEB_CONCURRENCY=1`. Confira as duas variáveis em *radar-inpi-api → Environment*. Um serviço criado antes dessa configuração pode não ter as duas. Se faltar alguma ou o valor estiver diferente, corrija e publique de novo pelo painel, se o Render não fizer isso sozinho. O processamento no Render, manual ou automático, ainda não foi testado.

- A API precisa de **um único processo**, pois cada processo teria o próprio agendamento. O uvicorn lê a variável `WEB_CONCURRENCY`, que o [Render pode definir sozinho](https://render.com/docs/environment-variables). Por isso o `render.yaml` a fixa em `1`.
- O agendamento roda às terças e quartas, às 9h, 13h e 18h (horário de Brasília).
- Cerca de 30 segundos depois que a API sobe, ele faz uma verificação. Ela tenta processar as edições que ainda não estão "Processada", entre a edição da terça mais recente e até 3 edições anteriores, sem voltar antes da edição mais antiga já registrada. Com o banco vazio, só a edição mais recente.
- No fim de cada execução, o sistema tenta enviar os e-mails dos alertas pendentes.

**Banco novo, sem ativos:** cerca de 30 segundos depois da primeira subida, a verificação pode processar a edição da terça mais recente antes de qualquer ativo ser cadastrado. Nesse caso a edição fica como "Processada", sem despachos, e o agendamento não a repete. Depois de cadastrar os ativos, processe essa edição de novo pelo `/docs`, informando o número dela (veja "Processar a RPI manualmente"). O número aparece em **GET /api/rpi/editions**. O mesmo vale para qualquer ativo cadastrado depois que uma edição já foi processada.

**E-mail na publicação:**
- O `render.yaml` não define as variáveis `SMTP_*`. Decida como os e-mails serão enviados **antes** do primeiro processamento com ativos reais: os alertas criados enquanto `SMTP_HOST` estiver vazio não recebem e-mail depois.
- Sem `SMTP_HOST`, o e-mail não é enviado: ele só aparece na aba *Logs* do Render, e **o alerta é marcado como enviado** mesmo assim. Configurar o SMTP depois não reenvia esses alertas. Eles continuam na tela de Alertas.
- O Render anunciou que os serviços web gratuitos [bloqueiam a saída para as portas SMTP 25, 465 e 587](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports). Pelo anúncio, para usar essas portas é preciso um plano pago. Outra porta ou outro provedor de e-mail não foi testado neste projeto.

### Atualizações

Depois do merge na `main`, publique de novo no painel de cada serviço, se ele ainda não tiver feito isso sozinho. A opção de publicação automática fica nas configurações de cada um.

### Limites dos planos gratuitos

Consultados na documentação do Render em 28/11/2026:
- **O banco PostgreSQL gratuito expira 30 dias depois de criado.** Depois disso há 14 dias de tolerância e ele é apagado. Para uso real por mais tempo, antes do vencimento é preciso passar o banco para um plano pago ou para outro serviço de PostgreSQL. Basta trocar a `DATABASE_URL`.
- A API gratuita "dorme" depois de 15 minutos sem acesso. O primeiro acesso seguinte demora cerca de um minuto.
- Enquanto a API dorme, nada roda nela: a coleta automática da RPI não acontece nesses períodos. Com a coleta ligada (como no `render.yaml`), quando a API acorda (no primeiro acesso) ou é publicada de novo, a verificação feita cerca de 30 segundos depois da subida tenta processar as edições que ficaram pendentes (veja "Coleta automática da RPI"). Também é possível processar pelo `/docs` (veja "Processar a RPI manualmente").

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

## Licença

Este projeto é distribuído sob a **Apache License 2.0**. O texto completo está no arquivo [`LICENSE`](LICENSE).
