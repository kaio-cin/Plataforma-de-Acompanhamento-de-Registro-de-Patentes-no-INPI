# Radar INPI: o que falta e divisão entre os 5 membros

Atualizado em 26/11/2026 · Apresentação final (Sprint 4): **07/12/2026**

## 1. Onde o projeto está

O último código de funcionalidade entrou em 22/out. Depois disso vieram testes, refatoração e relatórios (até 15/nov).

| Etapa | Histórias | Situação |
|---|---|---|
| Step 1: Login e perfis | US01, US02, US03 | Pronto |
| Step 2: Cadastro de ativos | US04, US06, US07 | Pronto |
| | **US05: editar ativo** | Falta (não existe rota nem tela) |
| **Step 3: Coleta da RPI** | **US08, US09, US10** | Falta tudo |
| **Step 4: Alertas** | **US11, US12, US13** | Falta tudo (o menu mostra "em breve") |
| **Step 5: Linha do tempo** | **US14** | Falta tudo |

Além das histórias, faltam: publicar o sistema, README, seed de demonstração, testes das novas partes e 9 itens de dívida técnica abertos (DT-04, DT-06 a DT-13, em `docs/qualidade/divida-tecnica.md`).

## 2. Quem já contribuiu e a meta de equilíbrio

| Membro | Conta | Commits até 26/11 | O que fez | Commits novos (meta) | Total previsto |
|---|---|---|---|---|---|
| Kaio | `kaio-cin` | 8 | Estrutura, models, login, cadastro, front-end inteiro | ~5 | ~13 |
| Breno | `bacr-cin` | 14 | Testes, cobertura, dívida técnica, refatorações | ~2 | ~16 |
| Fred | `fred-cin` | 4 (só PDFs) | Nenhum código ainda | ~10 | ~14 |
| David | | 0 | | ~13 | ~13 |
| Guilherme | | 0 | | ~13 | ~13 |

Cada membro termina com 13 a 16 commits e pelo menos uma US com o seu nome.

## 3. A divisão por pessoa

A divisão segue o caminho do dado: **a RPI entra** (Fred) → **vira alerta** (David) → **aparece no painel e na linha do tempo** (Guilherme) → **fica publicado e documentado** (Kaio) → **é testado e validado** (Breno).

### Fred: coleta e cruzamento da RPI (US08, US09, US10)

Back-end
- Models (fazer primeiro, os outros dependem deles): `RpiEdition`, `Dispatch`, `DispatchCode`.
- Coletor: baixa o XML da RPI em revistas.inpi.gov.br e guarda o arquivo.
- Parser: lê o XML e extrai número do processo, código e texto do despacho.
- Cruzamento (US09): compara com os `process_number` cadastrados (normalizando espaços, pontos e hífens) e grava os `Dispatch`.
- Agendamento (US08): tarefa toda terça (APScheduler) e rota `POST /api/rpi/process` para disparar manualmente (essencial para a demo).
- `GET /api/rpi/editions` (US10, só NIT).
- Ao gravar um despacho, chama `create_alerts_for(db, dispatch)` do David.
- Testes do parser e do cruzamento com um XML real em `tests/fixtures/`.

Commits sugeridos (~10): `feat(models): RpiEdition, Dispatch e DispatchCode` · `test(rpi): fixture XML de exemplo` · `feat(rpi): download do XML` · `feat(rpi): parser de despachos` · `test(rpi): testes do parser` · `feat(rpi): cruzamento com processos (US09)` · `test(rpi): testes do cruzamento` · `feat(rpi): rota de processamento manual` · `feat(rpi): agendamento semanal (US08)` · `feat(api): edições processadas (US10)`

### David: alertas e notificações (US11, US12, US13)

Back-end
- Model `Alert`.
- `create_alerts_for(db, dispatch)`: um alerta para cada usuário NIT e para o autor vinculado (US13).
- E-mail (US11): SMTP (Gmail com senha de app ou Mailtrap); em desenvolvimento só imprime no terminal. Configurações no `.env`.
- Rotas: `GET /api/alerts`, `PATCH /api/alerts/{id}/read`, `GET /api/alerts/unread-count`.

Front-end
- Tela Alertas (US12): filtros (todos, não lidos, exigem ação), prazo em destaque, "marcar como lido", link para o ativo.
- Sininho com contador de não lidos na barra superior.
- Ativar "Alertas" no menu (`Sidebar.jsx`).

Commits sugeridos (~13): `feat(models): Alert` · `feat(alerts): função create_alerts_for` · `feat(alerts): alerta para o autor vinculado (US13)` · `feat(alerts): cálculo do prazo` · `feat(email): configuração SMTP no .env` · `feat(email): envio de alerta por e-mail (US11)` · `feat(api): listagem de alertas (US12)` · `feat(api): marcar como lido e contador` · `test(alerts): testes das rotas e permissões` · `feat(front): api de alertas` · `feat(front): tela de alertas` · `feat(front): contador na barra superior` · `feat(front): ativa Alertas no menu`

### Guilherme: edição de ativos e linha do tempo (US05, US14, front da US10)

Back-end
- `PUT /api/assets/{id}`: editar ativo, só NIT (inclui trocar o autor vinculado).
- `GET /api/assets/{id}`: detalhe, respeitando o perfil (autor só vê o que é dele).
- `GET /api/assets/{id}/timeline`: despachos do processo em ordem de data (lê a tabela `dispatches` do Fred).

Front-end
- Tela Detalhe do ativo (`/ativos/:id`): dados e linha do tempo vertical, destacando despachos que exigem ação.
- Tela Editar ativo (`/ativos/:id/editar`), reaproveitando o formulário de `NewAssetPage`.
- Linhas da tabela da carteira clicáveis, levando ao detalhe.
- Tela Edições da RPI (NIT): tabela com status e botão "Processar agora" (usa as rotas do Fred).

Commits sugeridos (~13): `feat(schemas): AssetUpdate` · `feat(api): edição de ativo (US05)` · `feat(api): detalhe do ativo` · `feat(api): timeline do ativo (US14)` · `test(assets): testes de edição e detalhe` · `feat(front): api de detalhe e edição` · `feat(front): tela de detalhe do ativo` · `feat(front): componente de linha do tempo` · `feat(front): tela de edição (US05)` · `feat(front): linhas da carteira clicáveis` · `feat(front): api de edições RPI` · `feat(front): tela de edições da RPI (US10)` · `feat(front): botão Processar agora`

### Kaio: publicação, glossário e documentação final

- Popular a tabela `DispatchCode` com os códigos oficiais do INPI (seções 200 e 700), marcando quais exigem ação e o prazo.
- Tela Glossário de despachos: códigos explicados em linguagem simples; ativar no menu.
- Deploy: back-end no Render com PostgreSQL gratuito e front-end na Vercel; configurar `DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ORIGINS`.
- README na raiz e roteiro da demo.

Commits sugeridos (~5): `chore(seed): códigos de despacho 200/700` · `feat(front): glossário de despachos` · `chore: suporte a PostgreSQL` · `chore: deploy Render/Vercel` · `docs: README e roteiro da demo`

### Breno: qualidade e validação final

- Resolver **DT-13** (a lista inteira quebra com um dado antigo), que vira risco real quando dados da RPI entrarem.
- Teste e2e (Playwright) do fluxo completo: login → processar RPI → alerta aparece → abrir linha do tempo; atualizar a matriz de rastreabilidade com as US novas.
- Revisar os Pull Requests dos outros antes do merge.

Commits sugeridos (~2): `fix: DT-13 schema de saída independente da entrada` · `test(e2e): fluxo RPI → alerta → timeline + matriz atualizada`

## 4. Dependências e combinados do dia 1

A dependência forte é: **Fred cria os models → David, Guilherme e Kaio usam**. Para ninguém ficar parado:

1. Combinar os campos dos models `Dispatch`, `DispatchCode` e `Alert`. O Fred commita só os models logo no início.
2. Combinar a assinatura `create_alerts_for(db, dispatch)`. O David começa com uma versão vazia e o Fred já pode chamar.
3. Combinar o formato JSON de `/timeline`, `/alerts` e `/rpi/editions`, para o front-end ser feito com dados falsos enquanto o back-end não fica pronto.

Arquivos compartilhados (risco de conflito): `models/__init__.py`, `main.py`, `App.jsx`, `Sidebar.jsx`, `seed.py`. Regra: alterações pequenas, `git pull` antes de mexer, commit logo em seguida.

## 5. Cronograma até 07/12

| Quando | Fred | David | Guilherme | Kaio | Breno |
|---|---|---|---|---|---|
| 27–28/nov | Models, fixture e parser | E-mail (SMTP); depois o model Alert | US05 no back-end | Códigos de despacho | Ajudar a configurar o ambiente dos 3 novos |
| 29/nov–01/dez | Download, cruzamento e rota manual | Rotas de alertas | Detalhe e timeline (back e front) | Glossário | DT-13 |
| 02–03/dez | Agendamento e rota de edições | Tela de alertas e contador | Edição e tela de edições da RPI | Deploy | Revisão de PRs |
| **04/dez** | **Integração: todos juntam na `main` e testam o fluxo completo** | | | | |
| 05/dez | Testes da RPI | Testes de alertas | Testes de ativos | README e demo | e2e e matriz |
| **06/dez** | **Congelamento do código e ensaio** | | | | |
| 07/dez | Apresentação | | | | |

## 6. Fluxo de Git

1. Cada pessoa trabalha em branches por tarefa, no formato `tipo/assunto` (exemplos: `feat/rpi-models`, `feat/alertas-email`, `feat/ativos-edicao`, `chore/deploy`, `test/e2e-fluxo`).
2. Commits pequenos e frequentes, sempre da própria conta, com o Git configurado com o nome e o e-mail dela.
3. Ao terminar uma parte: `git pull origin main`, resolver conflitos, abrir Pull Request, outra pessoa revisa, merge.
4. No merge, usar **"Create a merge commit"**. Não usar "Squash and merge".
5. Antes de cada merge: `pytest` e `npm test` passando.

## 7. Se o tempo apertar

**Obrigatório para a demo:** US05, cruzamento da RPI com disparo manual (US09), alertas no painel (US12), linha do tempo (US14) e sistema publicado.

**Pode ser simplificado:** e-mail real (mostrar no terminal), agendamento semanal (mostrar a configuração e usar o botão manual), glossário.

**Fora do escopo** (deixar "em breve"): Calendário, Tarefas e Relatórios.
