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
