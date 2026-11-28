# Glossário de despachos do INPI

Tabela `dispatch_codes`: o que cada código de despacho da RPI significa, se exige ação e qual é o prazo. Os dados ficam em `backend/app/dispatch_codes_data.py` e a carga em `backend/app/seed_codes.py`.

## Fonte

| | Patentes | Programas de computador |
|---|---|---|
| Documento | Tabela de Códigos de Despachos - Patentes | Tabela de Códigos de Despachos - Programas de Computador |
| Arquivo recebido | `tabela-despachos.pdf` (46 páginas) | `tabela-despachos-1.pdf` (5 páginas) |
| Endereço (URL) | https://revistas.inpi.gov.br/rpi/download/despachos/200 | https://revistas.inpi.gov.br/rpi/download/despachos/700 |
| Versão | o PDF não informa | o PDF não informa |
| Data de consulta | 27/11/2026 | 27/11/2026 |
| Códigos | 314 | 47 |

A data de consulta vem do metadado `CreationDate` dos PDFs (27/11/2026, 22h29, horário de Brasília). Os PDFs são gerados pelo sistema do INPI (JasperReports) no momento do download.

## Como carregar

```
python -m app.seed_codes      (só os códigos; serve para produção)
python -m app.seed            (demonstração: usuários, ativos e códigos)
```

A carga é idempotente pela chave (tipo de ativo, código). Rodar de novo atualiza descrições e prazos corrigidos. Nenhum código é apagado.

## O que cada coluna guarda

- `code`: código como na tabela oficial, inclusive o zero à esquerda dos programas (`080` a `099`).
- `official_description`: título do código, exatamente como na tabela. É o mesmo texto que a RPI publica em `<titulo>` (há um teste que confere isso com as fixtures da RPI 2916). O texto explicativo da tabela oficial passa de 500 caracteres em vários códigos e por isso não é copiado.
- `plain_description`: explicação em linguagem simples, escrita pela equipe a partir do texto oficial.
- `requires_action` e `deadline_days`: ver os critérios abaixo.

## Critérios

**Exige ação** (`requires_action = True`) quando:
- se ninguém agir, o ativo é prejudicado (arquivamento, indeferimento definitivo, extinção, nulidade);
- ou se perde a única chance de reverter uma decisão contra o ativo (recurso contra indeferimento, arquivamento, retirada);
- ou um pedido do próprio titular foi negado ou está em exigência (transferência, alteração de nome, sede ou endereço).

**Não exige ação**:
- despacho informativo ou favorável;
- prazo que é de terceiros (contrarrazões de terceiros, os 6 meses para nulidade depois da concessão);
- opção que, se ignorada, não prejudica o ativo (anúncio na Vitrine de PI, trâmite prioritário).

**Prazo** (`deadline_days`) só quando a tabela dá o prazo em dias, contado desta publicação ("desta data", "a partir da data desta publicação") e sem condição, e só em código que exige ação. O sistema calcula publicação + dias corridos. A tabela nunca fala em dias úteis e, quando detalha a contagem, diz "dias corridos".

Nos outros casos o prazo fica vazio e é explicado no texto simples. O alerta mostra então "Ação necessária, prazo não definido".

## Números

| | Exige ação, com prazo | Exige ação, sem prazo | Não exige ação |
|---|---|---|---|
| Patentes | 45 (30 dias: 1; 60 dias: 37; 90 dias: 7) | 31 | 238 |
| Programas | 10 (30 dias: 1; 60 dias: 9) | 0 | 37 |

## Decisões onde a tabela deixa margem

Pontos em que a tabela oficial deixa margem e a equipe escolheu um critério. Cada um se resolve mudando uma linha em `dispatch_codes_data.py` e rodando a carga de novo.

Confirmado em 28/11/2026:
- **Programa 082:** a "data da notificação" é a própria publicação na RPI, então o prazo é de 60 dias da publicação.
- **Patente 1.3, 3.1 e 3.2:** o NIT quer receber o aviso do pagamento do exame (exige ação, sem data).
- **Regra geral:** código sem nenhuma providência a tomar é só informativo, não "exige ação". Por isso 120, 12.6 e 15.22.2 continuam informativos.

| Códigos | Escolha | Por quê | Situação |
|---|---|---|---|
| Patente 1.3, 3.1, 3.2 | exige ação, sem prazo | Lembram que o exame precisa ser pago em 36 meses contados do depósito (não da publicação), e só se ainda não foi pago. | Confirmada |
| Patente 2.10 | exige ação, sem prazo | Procuração em 60 dias contados do depósito, só quando houve procurador. | Critério da equipe |
| Patente 2.7, 7.3, 8.10, 10.8, 11.15, 12.8 | exige ação, sem prazo | Republicações em que a tabela diz que o prazo recomeça se o despacho republicado pedia providência. As outras republicações seguem o texto delas. | Critério da equipe |
| Patente 6.10 | exige ação, sem prazo | 90 ou 60 dias, conforme a exigência original. | Critério da equipe |
| Patente 6.6.1 | exige ação, 60 dias | A falta de resposta não arquiva; o INPI considera que não houve acesso ao patrimônio genético. | Critério da equipe |
| Patente 9.1.1, 9.1.2, 9.2.4.1, 1.2.2, 1.4.3, 4.3.1 | exige ação, 60 dias | Anulam uma decisão favorável ou reabrem o recurso contra uma desfavorável. | Critério da equipe |
| Patente 8.6, 21.6 | exige ação, sem prazo | Restauração em 3 meses: prazo em meses. | Critério da equipe |
| Patente 11.34, 15.34.2, 15.34.3, 22.34.2, 22.34.3 | exige ação, sem prazo | Os documentos podem ser apresentados "a qualquer tempo". | Critério da equipe |
| Patente 15.34, 22.34, 24.2 | exige ação, sem prazo | A tabela dá 60 dias, mas não diz a partir de quando. | Critério da equipe |
| Patente 15.22, 22.11, 140, 218 | exige ação, sem prazo | Devolução de prazo: o novo prazo vem em cada despacho. | Critério da equipe |
| Patente 15.22.2 | não exige ação | Sinaliza uma devolução de prazo por falha de sistema já decidida; não pede providência. | Confirmada (regra geral) |
| Patente 23.4, 24.1, 24.3, 121, 205 | exige ação, sem prazo | O título indica exigência ou manifestação, mas a tabela não traz texto com prazo. | Critério da equipe |
| Patente 120 | não exige ação | "Tome conhecimento do parecer técnico", sem prazo nem consequência na tabela. | Confirmada (regra geral) |
| Patente 12.6 | não exige ação | Os 60 dias são para contrarrazões de interessados, não uma providência obrigatória. | Confirmada (regra geral) |
| Patente 18.7 | não exige ação | A exigência é para quem pediu a caducidade, não para o titular. | Critério da equipe |
| Programa 082 | exige ação, 60 dias | A tabela conta o prazo "da data da notificação", que é a própria publicação na RPI. | Confirmada |
| Programa 080 | não exige ação | O texto da tabela está truncado ("Formulada exigência ... formulada."). | Critério da equipe |
| Programa 115 | exige ação, 30 dias | Recurso de terceiro contra o deferimento: o titular pode apresentar contrarrazões. | Critério da equipe |

## O que o modelo não representa

- **Prazo em meses** (8.6, 21.6; 36 meses do exame em 1.3, 3.1 e 3.2): fica sem data.
- **Prazo contado de outro marco** (depósito, pagamento de GRU): fica sem data.
- **Prazo condicional ou que depende do despacho anterior** (republicações, 6.10, 7.3).
- **Prazo informado só no complemento** de cada despacho (devoluções de prazo).
- **Fins de semana e feriados:** a data é publicação + dias corridos, sem prorrogação para dia útil.
- **Despacho que anula outro** (por exemplo, 111 de programas): o alerta do despacho anulado continua valendo.
- **Mudanças posteriores no glossário:** um alerta já criado guarda "exige ação" e prazo do momento em que foi criado. Só a explicação simples é lida do glossário na hora.

## Observações sobre a própria tabela oficial

- Programa 107: o título termina em "homologad" (truncado). Foi mantido como está.
- Patente 141: o prazo aparece como "60 (noventa) dias".
- Patente 25.11 e 25.12: o texto de "Republicação" e o de "Publicação Anulada" parecem trocados.
- Patente 6.21 e 6.23: títulos iguais, exceto pela maiúscula em "Pedidos"/"pedidos".
- Patente 100 e 100.1: título e texto iguais.
- Vários códigos só têm título, sem texto explicativo (por exemplo, 15.7 a 15.9, 23.x, 102 a 116, 130 a 140, 200 a 220).
- Os mesmos números aparecem nas duas tabelas com sentidos diferentes (por exemplo, 100, 111 e 120). Por isso a chave é (tipo de ativo, código).

## Como atualizar

1. Baixe de novo a tabela oficial e registre a data de consulta em `FONTE`.
2. Altere as linhas em `dispatch_codes_data.py`, mantendo o título exatamente como na tabela.
3. Rode `pytest tests/test_dispatch_codes_data.py tests/test_seed_codes.py`.
4. Rode `python -m app.seed_codes` no ambiente que deve receber a atualização.
