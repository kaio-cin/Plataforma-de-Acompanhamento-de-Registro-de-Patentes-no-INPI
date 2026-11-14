# Matriz de rastreabilidade — Sprint 3 (Parte 1)

Requisito → partições/limites → casos de teste. Projeto manual feito **antes** da geração da suíte pela LLM
(Etapa 1); as colunas "Coberto pela v1/v2" são preenchidas nas Etapas 3 e 4.

Escopo: back-end (FastAPI). User stories implementadas até a Sprint 2 com regras de negócio: US01, US02, US03,
US04, US06 e US07 (US05, edição, ainda não foi implementada). Os critérios de aceitação foram escritos pela equipe
no formato Dado/Quando/Então a partir das user stories e das decisões registradas na Sprint 2.

## 1. User stories selecionadas

- **US01** — Como membro da equipe do NIT, quero fazer login no sistema, para acessar a gestão da carteira de ativos.
- **US02** — Como autor/inventor, quero fazer login com acesso restrito, para acompanhar apenas os meus próprios processos.
- **US03** — Como membro do NIT, quero que o sistema diferencie os dois perfis de acesso, para que o autor não veja dados de outros processos.
- **US04** — Como membro do NIT, quero cadastrar um novo ativo (patente ou programa de computador) com título, natureza, inventores/autores, código do processo, data de depósito e situação atual, para começar a monitorá-lo.
- **US06** — Como membro do NIT, quero ver uma lista consolidada de todos os ativos com status atual, para ter visão geral da carteira.
- **US07** — Como membro do NIT, quero associar um autor/inventor a um ativo, para que ele tenha acesso de acompanhamento ao processo correspondente.

## 2. Critérios de aceitação

| ID | Critério |
|---|---|
| CA01-1 | Dado um usuário NIT com e-mail e senha corretos, quando faz login, então recebe um token JWT (tipo bearer) e os dados do usuário com perfil NIT. |
| CA01-2 | Dado um e-mail cadastrado e uma senha incorreta, quando faz login, então recebe 401 com a mensagem "E-mail ou senha incorretos.". |
| CA01-3 | Dado um e-mail não cadastrado, quando faz login, então recebe 401 com a mesma mensagem do CA01-2 (não revela quais e-mails existem). |
| CA01-4 | Dado um e-mail cadastrado digitado com maiúsculas, quando faz login com a senha correta, então o login funciona. |
| CA01-5 | Dado um e-mail com formato inválido ou uma senha vazia, quando faz login, então recebe 422 (requisição malformada). |
| CA01-6 | Dado o formulário OAuth2 (botão Authorize do Swagger), quando envia e-mail no campo username e a senha, então o comportamento é o mesmo do login JSON. |
| CA02-1 | Dado um autor com e-mail e senha corretos, quando faz login, então recebe token e perfil AUTOR. |
| CA02-2 | Dado um autor logado, quando lista os ativos, então recebe somente os ativos vinculados a ele. |
| CA02-3 | Dado um autor sem nenhum ativo vinculado, quando lista os ativos, então recebe uma lista vazia. |
| CA03-1 | Dado um usuário AUTOR, quando tenta cadastrar um ativo, então recebe 403 "Seu perfil não tem permissão para esta ação.". |
| CA03-2 | Dada uma requisição sem token, quando acessa uma rota protegida (listar, cadastrar, /me), então recebe 401. |
| CA03-3 | Dado um token malformado, assinado com outra chave ou expirado, quando acessa uma rota protegida, então recebe 401 "Sessão inválida ou expirada. Faça login novamente.". |
| CA03-4 | Dado um token bem assinado cujo usuário não existe mais (ou cujo sub não é um id), quando acessa uma rota protegida, então recebe 401. |
| CA03-5 | Dado um usuário logado, quando consulta /auth/me, então recebe os próprios dados (id, e-mail, perfil). |
| CA04-1 | Dado um NIT logado e dados válidos, quando cadastra um ativo, então recebe 201 com o ativo criado e ele passa a constar na listagem. |
| CA04-2 | A natureza do ativo deve ser "Patente" ou "Programa de Computador"; qualquer outro valor é recusado com 422. |
| CA04-3 | O título deve ter de 3 a 500 caracteres efetivos; espaços repetidos e nas bordas são normalizados e não contam. Fora disso, 422. |
| CA04-4 | O número do processo deve ter de 5 a 50 caracteres efetivos e é gravado normalizado (maiúsculas e espaços simples). Fora disso, 422. |
| CA04-5 | Dado um número de processo já cadastrado (inclusive se diferir só por maiúsculas/espaços), quando cadastra, então recebe 409 com o número na mensagem. |
| CA04-6 | A data de depósito não pode estar no futuro (hoje é aceito); data futura ou inexistente é recusada com 422. |
| CA04-7 | A situação atual deve ter de 2 a 100 caracteres efetivos. Fora disso, 422. |
| CA04-8 | Os inventores/autores devem ter de 2 a 1000 caracteres efetivos. Fora disso, 422. |
| CA04-9 | Título, natureza, processo, data, situação e autores são obrigatórios; a ausência de qualquer um gera 422. |
| CA06-1 | Dado um NIT logado, quando lista os ativos, então recebe todos os ativos da carteira (com ou sem autor vinculado). |
| CA06-2 | A lista vem ordenada da data de depósito mais recente para a mais antiga; em empate, o cadastrado por último vem primeiro. |
| CA06-3 | Cada item traz título, natureza, processo, data, situação atual, autores e o e-mail do autor vinculado (ou nulo). |
| CA06-4 | Dada uma carteira vazia, quando o NIT lista os ativos, então recebe 200 com lista vazia. |
| CA07-1 | Dado o e-mail de um usuário AUTOR cadastrado, quando o NIT cadastra o ativo com ele, então o ativo fica vinculado e o autor passa a vê-lo (e só ele, entre os autores). |
| CA07-2 | Dado um e-mail não cadastrado, quando o NIT tenta vincular, então recebe 422 e o ativo não é gravado. |
| CA07-3 | Dado o e-mail de um usuário NIT, quando o NIT tenta vinculá-lo como autor, então recebe 422. |
| CA07-4 | Dado o campo de autor ausente, vazio ou só com espaços, quando o NIT cadastra, então o ativo é criado sem vínculo. |
| CA07-5 | Dado o e-mail de um AUTOR digitado com maiúsculas, quando o NIT vincula, então o autor correto é encontrado. |
| CA07-6 | Dado um e-mail de autor com formato inválido, quando o NIT cadastra, então recebe 422. |

## 3. Partições de equivalência

| ID | Variável | Partição | Tipo | Representante | Resultado esperado |
|---|---|---|---|---|---|
| P01 | e-mail (login) | e-mail de usuário NIT cadastrado | válida | nit@teste.edu.br | 200, perfil NIT |
| P02 | e-mail (login) | e-mail de usuário AUTOR cadastrado | válida | autora@teste.edu.br | 200, perfil AUTOR |
| P03 | e-mail (login) | e-mail cadastrado com caixa diferente | válida | NIT@Teste.EDU.br | 200 |
| P04 | e-mail (login) | formato válido, não cadastrado | inválida | ninguem@teste.edu.br | 401 genérico |
| P05 | e-mail (login) | formato inválido | inválida | nao-e-email | 422 |
| P06 | senha | senha correta | válida | senha-teste-123 | 200 |
| P07 | senha | senha incorreta não vazia | inválida | errada | 401 genérico |
| P08 | senha | senha vazia | inválida | "" | 422 |
| P09 | canal de login | JSON em /auth/login | válida | {email, password} | 200 |
| P10 | canal de login | formulário OAuth2 em /auth/token | válida | username=…&password=… | 200 |
| P11 | token | token válido de usuário existente | válida | token do login | 200 |
| P12 | token | sem cabeçalho Authorization | inválida | — | 401 |
| P13 | token | token malformado | inválida | "token-falso" | 401 |
| P14 | token | assinado com outra chave | inválida | JWT com chave "outra" | 401 |
| P15 | token | token expirado | inválida | exp = agora − 1 s | 401 |
| P16 | token | sub não numérico | inválida | sub = "abc" | 401 |
| P17 | token | usuário do token não existe | inválida | sub = "9999" | 401 |
| P18 | perfil | NIT | válida | nit@teste.edu.br | pode cadastrar |
| P19 | perfil | AUTOR | inválida p/ cadastro | autora@teste.edu.br | 403 no cadastro |
| P20 | título | 3 a 500 caracteres efetivos | válida | "Método de compostagem" | 201 |
| P21 | título | menos de 3 caracteres | inválida | "ab" | 422 |
| P22 | título | mais de 500 caracteres | inválida | 501 × "a" | 422 |
| P23 | título | somente espaços | inválida | "     " | 422 |
| P24 | título | válido com espaços extras | válida | "  Método   de  teste " | 201, gravado "Método de teste" |
| P25 | natureza | "Patente" | válida | Patente | 201 |
| P26 | natureza | "Programa de Computador" | válida | Programa de Computador | 201 |
| P27 | natureza | qualquer outro valor | inválida | "Marca" | 422 |
| P28 | nº do processo | 5 a 50 caracteres efetivos | válida | "BR 10 2025 000999-9" | 201 |
| P29 | nº do processo | menos de 5 caracteres | inválida | "BR10" | 422 |
| P30 | nº do processo | mais de 50 caracteres | inválida | 51 × "9" | 422 |
| P31 | nº do processo | minúsculas / espaços repetidos | válida | "br 10  2025   000999-9" | 201, normalizado |
| P32 | nº do processo | já cadastrado (mesmo após normalizar) | inválida | "br 10 2023 000001-1" | 409 |
| P33 | nº do processo | somente espaços | inválida | "       " | 422 |
| P34 | data de depósito | data passada | válida | 2025-02-14 | 201 |
| P35 | data de depósito | data futura | inválida | amanhã | 422 |
| P36 | data de depósito | data inexistente / formato inválido | inválida | "2023-02-30" | 422 |
| P37 | situação | 2 a 100 caracteres efetivos | válida | "Em análise" | 201 |
| P38 | situação | menos de 2 caracteres | inválida | "A" | 422 |
| P39 | situação | mais de 100 caracteres | inválida | 101 × "s" | 422 |
| P40 | situação | somente espaços | inválida | "    " | 422 |
| P41 | autores | 2 a 1000 caracteres efetivos | válida | "Fulano, Beltrana" | 201 |
| P42 | autores | menos de 2 caracteres | inválida | "F" | 422 |
| P43 | autores | mais de 1000 caracteres | inválida | 1001 × "x" | 422 |
| P44 | autores | somente espaços | inválida | "    " | 422 |
| P45 | e-mail do autor (US07) | campo ausente / null | válida | — | 201 sem vínculo |
| P46 | e-mail do autor (US07) | vazio ou só espaços | válida | "" / "   " | 201 sem vínculo |
| P47 | e-mail do autor (US07) | AUTOR cadastrado | válida | autora@teste.edu.br | 201 vinculado |
| P48 | e-mail do autor (US07) | AUTOR cadastrado, caixa diferente | válida | AUTORA@TESTE.EDU.BR | 201 vinculado |
| P49 | e-mail do autor (US07) | usuário NIT | inválida | nit@teste.edu.br | 422 |
| P50 | e-mail do autor (US07) | não cadastrado | inválida | naoexiste@teste.edu.br | 422 |
| P51 | e-mail do autor (US07) | formato inválido | inválida | "nao-e-email" | 422 |
| P52 | carteira | vazia | válida | 0 ativos | 200 [] |
| P53 | carteira | vários ativos, visão NIT | válida | 3 ativos | todos, ordenados |
| P54 | carteira | autor com ativos vinculados | válida | autora | só os dela |
| P55 | carteira | autor sem ativos vinculados | válida | novo autor | 200 [] |
| P56 | payload do cadastro | campo obrigatório ausente | inválida | sem "title" (e demais) | 422 |

## 4. Valores-limite

| ID | Variável | Fronteira | Um lado | Outro lado |
|---|---|---|---|---|
| L01 | senha | tamanho mínimo 1 | 0 → 422 | 1 → passa da validação (401 se errada) |
| L02 | token | instante de expiração | exp = agora − 1 s → 401 | exp = agora + 60 s → 200 |
| L03 | título | mínimo 3 | 2 → 422 | 3 → 201 |
| L04 | título | máximo 500 | 500 → 201 | 501 → 422 |
| L05 | nº do processo | mínimo 5 | 4 → 422 | 5 → 201 |
| L06 | nº do processo | máximo 50 | 50 → 201 | 51 → 422 |
| L07 | data de depósito | hoje / amanhã | hoje → 201 | amanhã → 422 |
| L08 | situação | mínimo 2 | 1 → 422 | 2 → 201 |
| L09 | situação | máximo 100 | 100 → 201 | 101 → 422 |
| L10 | autores | mínimo 2 | 1 → 422 | 2 → 201 |
| L11 | autores | máximo 1000 | 1000 → 201 | 1001 → 422 |
| L12 | ordenação da lista | datas de depósito iguais (empate) | mesma data → desempate pelo id | — |
| L13 | título (efetivo) | mínimo 3 após normalizar espaços | "  ab  " (2 efetivos) → 422 | "  abc  " (3 efetivos) → 201 |

## 5. Matriz requisito → partição/limite → caso de teste

| Requisito / critério | Variável | Partição ou limite | Caso de teste esperado | Coberto pela v1? | Coberto pela v2? |
|---|---|---|---|---|---|
| US01 — CA01-1 | e-mail, senha, canal | P01 P06 P09 | **CT-01-01**: login JSON do NIT com senha correta → 200, token bearer, user.role = NIT e token decodifica role NIT | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US01 — CA01-2 | senha | P07 | **CT-01-02**: senha incorreta → 401 "E-mail ou senha incorretos." | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US01 — CA01-3 | e-mail | P04 | **CT-01-03**: e-mail não cadastrado → 401 com a mesma mensagem | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US01 — CA01-4 | e-mail | P03 | **CT-01-04**: "NIT@Teste.EDU.br" + senha correta → 200 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US01 — CA01-5 | e-mail | P05 | **CT-01-05**: "nao-e-email" → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US01 — CA01-5 | senha | P08 L01 | **CT-01-06**: senha "" (0 caracteres) → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US01 — CA01-2 | senha | L01 | **CT-01-07**: senha "x" (1 caractere, errada) → 401 (passa da validação) | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US01 — CA01-6 | canal | P10 | **CT-01-08**: formulário OAuth2 com credenciais corretas → 200, role NIT | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US01 — CA01-6 | canal, senha | P10 P07 | **CT-01-09**: formulário OAuth2 com senha errada → 401 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US02 — CA02-1 | e-mail | P02 | **CT-02-01**: login da autora → 200, role AUTOR | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US02 — CA02-2 | carteira | P54 | **CT-02-02**: autora lista → somente "Patente da autora" | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US02 — CA02-3 | carteira | P55 | **CT-02-03**: autor sem vínculos lista → 200 [] | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-1 | perfil | P19 | **CT-03-01**: AUTOR faz POST /assets → 403 com a mensagem de permissão | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-2 | token | P12 | **CT-03-02**: GET /assets sem token → 401 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-2 | token | P12 | **CT-03-03**: POST /assets sem token → 401 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-2 | token | P12 | **CT-03-04**: GET /auth/me sem token → 401 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-3 | token | P13 | **CT-03-05**: "Bearer token-falso" → 401 "Sessão inválida ou expirada…" | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-3 | token | P14 | **CT-03-06**: JWT assinado com outra chave → 401 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-3 | token | P15 L02 | **CT-03-07**: JWT com exp = agora − 1 s → 401 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-3 | token | L02 | **CT-03-08**: JWT com exp = agora + 60 s → 200 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-4 | token | P16 | **CT-03-09**: JWT válido com sub = "abc" → 401 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-4 | token | P17 | **CT-03-10**: JWT válido com sub de usuário inexistente → 401 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US03 — CA03-5 | token | P11 | **CT-03-11**: GET /auth/me com token da autora → 200 com e-mail e role AUTOR | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-1 | todas (representantes válidos) | P18 P20 P25 P28 P34 P37 P41 P45 | **CT-04-01**: NIT cadastra ativo válido → 201 com os campos enviados | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-1 | — | P53 | **CT-04-02**: ativo cadastrado aparece na listagem do NIT | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-2 | natureza | P26 | **CT-04-03**: "Programa de Computador" → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-2 | natureza | P27 | **CT-04-04**: "Marca" → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-3 | título | P21 L03 | **CT-04-05**: título com 2 caracteres → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-3 | título | L03 | **CT-04-06**: título com 3 caracteres → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-3 | título | L04 | **CT-04-07**: título com 500 caracteres → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-3 | título | P22 L04 | **CT-04-08**: título com 501 caracteres → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-3 | título | P23 | **CT-04-09**: título só com espaços → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-3 | título | P24 | **CT-04-10**: "  Método   de  teste " → 201 com título "Método de teste" | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-3 | título | L13 | **CT-04-11**: "  ab  " → 422 e "  abc  " → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-4 | nº do processo | P29 L05 | **CT-04-12**: processo com 4 caracteres → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-4 | nº do processo | L05 | **CT-04-13**: processo com 5 caracteres → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-4 | nº do processo | L06 | **CT-04-14**: processo com 50 caracteres → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-4 | nº do processo | P30 L06 | **CT-04-15**: processo com 51 caracteres → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-4 | nº do processo | P31 | **CT-04-16**: "br 10  2025   000999-9" → gravado "BR 10 2025 000999-9" | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-4 | nº do processo | P33 | **CT-04-17**: processo só com espaços → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-5 | nº do processo | P32 | **CT-04-18**: processo idêntico a um existente → 409 com o número na mensagem | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-5 | nº do processo | P32 | **CT-04-19**: processo que difere só por caixa/espaços → 409 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-6 | data de depósito | L07 | **CT-04-20**: data = hoje → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-6 | data de depósito | P35 L07 | **CT-04-21**: data = amanhã → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-6 | data de depósito | P36 | **CT-04-22**: "2023-02-30" → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-7 | situação | P38 L08 | **CT-04-23**: situação com 1 caractere → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-7 | situação | L08 | **CT-04-24**: situação com 2 caracteres → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-7 | situação | L09 | **CT-04-25**: situação com 100 caracteres → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-7 | situação | P39 L09 | **CT-04-26**: situação com 101 caracteres → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-7 | situação | P40 | **CT-04-27**: situação só com espaços → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-8 | autores | P42 L10 | **CT-04-28**: autores com 1 caractere → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-8 | autores | L10 | **CT-04-29**: autores com 2 caracteres → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-8 | autores | L11 | **CT-04-30**: autores com 1000 caracteres → 201 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-8 | autores | P43 L11 | **CT-04-31**: autores com 1001 caracteres → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-8 | autores | P44 | **CT-04-32**: autores só com espaços → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US04 — CA04-9 | payload | P56 | **CT-04-33**: cada campo obrigatório omitido, um por vez → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US06 — CA06-1 | carteira | P53 | **CT-06-01**: NIT lista → os 3 ativos, inclusive o sem autor | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US06 — CA06-2 | carteira | P53 | **CT-06-02**: ordem exata por data de depósito decrescente | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US06 — CA06-2 | ordenação | L12 | **CT-06-03**: duas datas iguais → o de maior id (cadastrado por último) primeiro | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US06 — CA06-3 | item da lista | P53 | **CT-06-04**: cada item traz todos os campos com os valores gravados (status atual incluso) | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US06 — CA06-4 | carteira | P52 | **CT-06-05**: carteira vazia → 200 [] | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-1 | e-mail do autor | P47 | **CT-07-01**: vincula a autora → 201, author_email e author_user_id preenchidos; autora passa a ver | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-1 | e-mail do autor | P47 | **CT-07-02**: outro autor não vê o ativo vinculado à autora | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-2 | e-mail do autor | P50 | **CT-07-03**: e-mail não cadastrado → 422 e o ativo não é gravado | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-3 | e-mail do autor | P49 | **CT-07-04**: e-mail de usuário NIT → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-4 | e-mail do autor | P46 | **CT-07-05**: author_email "" → 201 sem vínculo | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-4 | e-mail do autor | P46 | **CT-07-06**: author_email "   " → 201 sem vínculo | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-4 | e-mail do autor | P45 | **CT-07-07**: author_email ausente → 201 sem vínculo | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-5 | e-mail do autor | P48 | **CT-07-08**: "AUTORA@TESTE.EDU.BR" → vinculado à autora | (preencher na Etapa 3) | (preencher na Etapa 4) |
| US07 — CA07-6 | e-mail do autor | P51 | **CT-07-09**: "nao-e-email" → 422 | (preencher na Etapa 3) | (preencher na Etapa 4) |

## 6. Totais do projeto manual

- User stories: 6
- Critérios de aceitação: 33
- Partições de equivalência: 56 (25 válidas, 31 inválidas)
- Valores-limite (fronteiras): 13
- Casos de teste esperados: 70
