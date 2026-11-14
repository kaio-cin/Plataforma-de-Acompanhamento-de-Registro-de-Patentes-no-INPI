# Backlog de defeitos encontrados pelos testes (Sprint 3)

## BUG-01 — Campos de texto só com espaços (ou com espaços nas bordas) burlam o tamanho mínimo e quebram a listagem

| Campo | Valor |
|---|---|
| Encontrado por | Suíte v1 (LLM): `test_titulo_com_menos_de_3_caracteres_efetivos_retorna_422`. Ampliado pela v2 (partições "só espaços" de título, processo, situação e autores). |
| User story / critério | US04 — CA04-3, CA04-4, CA04-7, CA04-8; efeito colateral em US06 — CA06-1 |
| Severidade | **Alta**: um único cadastro inválido derruba a listagem da carteira inteira (500) para o NIT e para o autor vinculado. |
| Local | `backend/app/schemas/asset.py` — `AssetBase` (`Field(min_length=…)` + `@field_validator` em modo *after*) |
| Status | Aberto (testes da v2 marcados com `xfail(strict=True)` apontando para este item) |

**Como reproduzir**

1. Logado como NIT, `POST /api/assets/` com `"title": "   "` (ou `"status": "  "`, ou `"process_number": "      "`).
2. A API responde **500**, mas o ativo é gravado com o campo vazio.
3. `GET /api/assets/` passa a responder **500** para o NIT (e para o autor vinculado, se houver).

**Causa.** No Pydantic v2, as restrições declarativas do `Field` (`min_length`, `max_length`) são verificadas sobre o
valor bruto, e o `@field_validator` padrão (modo *after*) roda depois. O validador colapsa os espaços, então um valor
que tinha o tamanho mínimo só por causa dos espaços sai menor que o mínimo (ou vazio). O `create_asset` grava, e o
`response_model=AssetRead`, que herda as mesmas restrições, rejeita o objeto na saída.

O mesmo erro, no sentido oposto, rejeita valores válidos: um título com 499 caracteres e 4 espaços nas bordas
(503 brutos) é recusado, embora tenha 499 caracteres efetivos.

**Correção sugerida.** Normalizar **antes** de validar o tamanho: trocar os validadores para `mode="before"` (ou usar
`Annotated[str, BeforeValidator(_collapse_spaces), Field(min_length=…, max_length=…)]`). Com a correção, os testes
`xfail` da v2 passam a passar e o `strict=True` obriga a remover a marcação.
