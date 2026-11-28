"""Códigos de despacho do INPI carregados no glossário (tabela dispatch_codes).

Só dados: a validação e a carga ficam em app/seed_codes.py (python -m app.seed_codes).
Fonte, critérios e decisões a validar com o NIT: docs/glossario-despachos.md.

Como preencher cada código:
- official_description: título do código exatamente como na tabela oficial (é o mesmo texto que a RPI
  publica em <titulo>). O texto explicativo da tabela não cabe na coluna e fica resumido no
  plain_description.
- plain_description: explicação em linguagem simples para quem não é técnico, escrita pela equipe a partir
  do texto da tabela oficial.
- requires_action: True quando, se ninguém agir, o ativo é prejudicado (arquivamento, indeferimento
  definitivo, extinção, nulidade), quando se perde a única chance de reverter uma decisão contra ele ou
  quando um pedido do próprio titular foi negado ou está em exigência.
- deadline_days: só quando a tabela dá o prazo em dias, contado desta publicação ("desta data", "a partir
  da data desta publicação") e sem condição, e apenas em código que exige ação. Prazo em meses, contado de
  outro marco, condicional ou contraditório fica vazio (None) e é explicado no plain_description.

Nunca invente código, descrição oficial ou prazo: tudo vem da fonte registrada em FONTE.
"""

from dataclasses import dataclass
from datetime import date

from app.models.enums import AssetType


@dataclass(frozen=True)
class DispatchCodeEntry:
    """Um código de despacho como será gravado em dispatch_codes."""

    asset_type: AssetType
    code: str  # como publicado na RPI (ex.: "6.1"), sem espaços
    official_description: str
    plain_description: str
    requires_action: bool = False
    deadline_days: int | None = None  # dias corridos a partir da publicação; None sem prazo claro


@dataclass(frozen=True)
class FonteOficial:
    """De onde vieram os códigos de uma seção da RPI. None indica informação ainda pendente."""

    titulo: str | None = None
    url: str | None = None
    versao: str | None = None  # versão ou data do próprio documento
    data_consulta: date | None = None


# Fonte de cada seção, registrada separadamente. 200 e 700 são os números das seções no site do INPI, não
# faixas de códigos. Os PDFs são gerados pelo sistema do INPI no momento da consulta (metadado CreationDate
# de 27/11/2026) e não trazem número de versão.
FONTE: dict[AssetType, FonteOficial] = {
    AssetType.PATENTE: FonteOficial(
        titulo="Tabela de Códigos de Despachos - Patentes",
        url="https://revistas.inpi.gov.br/rpi/download/despachos/200",
        versao=None,  # o PDF não informa versão
        data_consulta=date(2026, 11, 27),
    ),
    AssetType.PROGRAMA_DE_COMPUTADOR: FonteOficial(
        titulo="Tabela de Códigos de Despachos - Programas de Computador",
        url="https://revistas.inpi.gov.br/rpi/download/despachos/700",
        versao=None,  # o PDF não informa versão
        data_consulta=date(2026, 11, 27),
    ),
}


def _patente(
    code: str,
    official_description: str,
    plain_description: str,
    *,
    requires_action: bool = False,
    deadline_days: int | None = None,
) -> DispatchCodeEntry:
    return DispatchCodeEntry(
        AssetType.PATENTE, code, official_description, plain_description, requires_action, deadline_days
    )


def _programa(
    code: str,
    official_description: str,
    plain_description: str,
    *,
    requires_action: bool = False,
    deadline_days: int | None = None,
) -> DispatchCodeEntry:
    return DispatchCodeEntry(
        AssetType.PROGRAMA_DE_COMPUTADOR,
        code,
        official_description,
        plain_description,
        requires_action,
        deadline_days,
    )


# --- Explicações repetidas em vários códigos ---------------------------------------------------------------------

_PUBLICACAO_ANULADA = (
    "O INPI cancelou uma publicação anterior deste processo porque ela saiu por engano. O complemento do "
    "despacho diz qual foi. Não é preciso fazer nada."
)
_DESPACHO_ANULADO = (
    "O INPI cancelou um despacho anterior deste processo porque ele foi indevido. O complemento do despacho "
    "diz qual foi e por quê. Não é preciso fazer nada."
)
_DECISAO_ANULADA = (
    "O INPI cancelou uma decisão anterior deste processo porque ela foi indevida. O complemento do despacho "
    "explica o motivo."
)
_RETIFICACAO = (
    "O INPI corrigiu um erro numa publicação anterior deste processo. Confira a correção no complemento do "
    "despacho."
)
_RETIFICACAO_SEM_MUDAR_PRAZO = (
    "O INPI corrigiu um erro numa publicação anterior deste processo. A correção não muda a data de "
    "publicação nem os prazos que já estavam correndo."
)
_REPUBLICACAO = (
    "O INPI publicou de novo um despacho deste processo porque a publicação anterior saiu com erro. Confira "
    "no complemento qual foi o despacho."
)
# Prazo condicional: só existe se o despacho republicado pedia providência (deadline_days vazio).
_REPUBLICACAO_REABRE_PRAZO = (
    "O INPI publicou de novo um despacho deste processo porque a publicação anterior saiu com erro. Se o "
    "despacho republicado pedia alguma providência, o prazo volta a contar desta publicação. Confira no "
    "complemento qual foi o despacho."
)
_PETICAO_NAO_CONHECIDA = (
    "O INPI não aceitou analisar uma petição deste processo. Confira o motivo no complemento do despacho."
)
_PETICAO_ARQUIVADA = "Uma petição deste processo foi arquivada. Confira o motivo no complemento do despacho."
_DEVOLUCAO_DE_PRAZO_SEM_TEXTO = (
    "O INPI devolveu um prazo neste processo. Confira no complemento qual é o novo prazo e o que precisa ser "
    "feito."
)
# Prazo variável, informado em cada despacho (deadline_days vazio).
_DEVOLUCAO_DE_PRAZO = (
    "O INPI devolveu um prazo que não pôde ser cumprido. O prazo adicional começa nesta publicação, tem no "
    "mínimo 15 dias e está indicado no despacho. Confira o complemento para saber o que fazer e até quando."
)
_RESTAURACAO_DOS_AUTOS = (
    "O INPI começou a restaurar (reconstituir) o processo e pede cópia de documentos (GRU 259, isenta). A "
    "tabela dá 60 dias, mas não diz a partir de quando contam; confira o complemento."
)
_DOCUMENTOS_A_QUALQUER_TEMPO = (
    "Não foi possível restaurar o processo com o que foi enviado. Os documentos pedidos podem ser enviados a "
    "qualquer momento (GRU 259), sem prazo."
)
_PRAZO_SEM_INICIO = "A tabela não informa o prazo; confira o complemento do despacho."
_CERTIFICADO_ATUALIZADO = (
    "O certificado de registro atualizado está disponível no portal do INPI. Não é preciso fazer nada."
)
_ANUIDADE_EM_MESES = "O prazo é em meses, por isso o sistema não calcula a data."


def _tramite_prioritario(motivo: str) -> str:
    return (
        f"Foi pedido trâmite prioritário (análise mais rápida) deste pedido, pelo motivo: {motivo}. A aceitação "
        "depende das regras. Não é preciso fazer nada agora."
    )


# --- Patentes (PDF "Tabela de Códigos de Despachos - Patentes", 46 páginas) ----------------------------------------

_PATENTES: tuple[DispatchCodeEntry, ...] = (
    # Pedido Internacional PCT/BR Designado ou Eleito (pp. 1-3)
    _patente(
        "1.1",
        "Pedido Internacional PCT Publicado. Petição de Requerimento de Entrada na Fase Nacional Recebida",
        "O pedido internacional (PCT) foi publicado pela OMPI e o INPI recebeu o pedido de entrada no Brasil. O "
        "INPI ainda vai analisar se ele pode ser aceito. Não é preciso responder; acompanhe os próximos despachos.",
    ),
    _patente(
        "1.1.1",
        "Retificação",
        "O INPI corrigiu um erro no aviso de publicação internacional e de entrada no Brasil. Não é preciso "
        "responder.",
    ),
    _patente(
        "1.1.2",
        "Publicação Anulada",
        "O INPI cancelou o aviso de publicação internacional e de entrada no Brasil porque ele saiu por engano. "
        "Não é preciso responder.",
    ),
    _patente(
        "1.1.3",
        "Republicação",
        "O INPI publicou de novo o aviso de publicação internacional e de entrada no Brasil porque o anterior "
        "saiu com erro. Não é preciso responder.",
    ),
    _patente(
        "1.2",
        "Pedido PCT Retirado",
        "O pedido internacional não entrou no Brasil porque prazos ou regras do PCT não foram cumpridos. Os "
        "motivos estão na Busca de Processos do INPI. Se discordar, é possível apresentar recurso (GRU 214) em "
        "até 60 dias da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "1.2.1",
        "Publicação Anulada",
        "O INPI cancelou a publicação da retirada do pedido internacional porque ela saiu por engano. Confira o "
        "complemento. Não é preciso responder.",
    ),
    _patente(
        "1.2.2",
        "Republicação",
        "O INPI publicou de novo a retirada do pedido internacional, que tinha saído com erro. Se discordar da "
        "retirada, é possível apresentar recurso (GRU 214) em até 60 dias desta publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "1.2.3",
        "Decisão Anulada",
        "O INPI cancelou a decisão que tinha retirado o pedido internacional, porque ela foi indevida. O motivo "
        "está no complemento. Não é preciso responder.",
    ),
    # Prazo de 36 meses contado do depósito internacional, e só se o exame ainda não foi pedido.
    _patente(
        "1.3",
        "Pedido PCT Admitido na Fase Nacional",
        "O pedido internacional entrou na fase nacional no Brasil. Atenção: o pedido de exame precisa ser pago "
        "em até 36 meses contados do depósito internacional (não desta publicação), senão o INPI arquiva o "
        "pedido. Se o exame já foi pago, não é preciso fazer nada.",
        requires_action=True,
    ),
    _patente(
        "1.3.1",
        "Retificação",
        "O INPI corrigiu um erro no aviso de entrada do pedido no Brasil. Confira o complemento. Não é preciso "
        "responder.",
    ),
    _patente(
        "1.3.2",
        "Publicação Anulada",
        "O INPI cancelou o aviso de entrada do pedido no Brasil porque ele saiu por engano. O motivo está no "
        "complemento. Não é preciso responder.",
    ),
    _patente(
        "1.3.3",
        "Republicação",
        "O INPI publicou de novo o aviso de entrada do pedido no Brasil porque o anterior saiu com erro.",
    ),
    _patente(
        "1.3.4",
        "Decisão Anulada",
        "O INPI cancelou a decisão de entrada do pedido no Brasil porque ela foi indevida. O motivo está no "
        "complemento. Não é preciso responder.",
    ),
    _patente(
        "1.4",
        "Restabelecimento de Direito à Entrada na Fase Nacional do PCT Concedido",
        "O INPI devolveu ao pedido internacional o direito de entrar no Brasil. Agora o INPI vai analisar se o "
        "pedido pode ser aceito. Não é preciso responder.",
    ),
    _patente(
        "1.4.1",
        "Restabelecimento de Direito à Entrada na Fase Nacional do PCT Negado",
        "O INPI negou o pedido para devolver ao pedido internacional o direito de entrar no Brasil. Os motivos "
        "estão no parecer. Se discordar, é possível apresentar recurso (GRU 214) em até 60 dias da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "1.4.2",
        "Publicação Anulada",
        "O INPI cancelou a publicação da decisão sobre o direito de entrada no Brasil porque ela saiu por "
        "engano. O motivo está no complemento. Não é preciso responder.",
    ),
    _patente(
        "1.4.3",
        "Republicação",
        "O INPI publicou de novo a decisão sobre o direito de entrada no Brasil, que tinha saído com erro. Se "
        "discordar, é possível apresentar recurso (GRU 214) em até 60 dias desta publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "1.4.4",
        "Decisão Anulada",
        "O INPI cancelou a decisão sobre o direito de entrada no Brasil porque ela foi indevida. O motivo está "
        "no complemento. Não é preciso responder.",
    ),
    _patente(
        "1.5",
        "Exigências Diversas",
        "O INPI parou a entrada do pedido no Brasil até que exigências sejam cumpridas. Veja o parecer na Busca "
        "de Processos do INPI e responda (GRU 207) em até 60 dias corridos da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "1.5.1",
        "Publicação Anulada",
        "O INPI cancelou a publicação da exigência porque ela saiu por engano. Confira o complemento. Não é "
        "preciso responder.",
    ),
    _patente(
        "1.5.2",
        "Republicação",
        "O INPI publicou de novo a exigência, que tinha saído com erro. É preciso cumpri-la (GRU 207) em até 60 "
        "dias corridos desta nova publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "1.5.3",
        "Exigência Anulada",
        "O INPI cancelou a exigência porque ela foi indevida. O motivo está no complemento. Não é preciso "
        "responder.",
    ),
    # Depósito (pp. 4-5)
    _patente(
        "2.1",
        "Pedido de Patente ou Certificado de Adição de Invenção Depositado",
        "O INPI concluiu a conferência inicial e considera o pedido depositado. O conteúdo fica em sigilo por 18 "
        "meses e depois é publicado. Não é preciso responder; acompanhe os próximos despachos.",
    ),
    _patente(
        "2.4",
        "Pedido Dividido Depositado",
        "O INPI aceitou a divisão do pedido. O pedido dividido tem a mesma data de depósito do original e segue "
        "na mesma fase. Não é preciso responder.",
    ),
    _patente(
        "2.5",
        "Exigência Formal Preliminar",
        "Na conferência inicial, o INPI encontrou problemas no pedido. Veja o parecer na Busca de Processos e "
        "envie os documentos corrigidos (GRU 206) em até 30 dias corridos da publicação. Sem resposta, o pedido "
        "não é aceito e a numeração é anulada.",
        requires_action=True,
        deadline_days=30,
    ),
    _patente(
        "2.6",
        "Publicação Anulada",
        "O INPI cancelou a publicação de um despacho deste pedido porque ela foi indevida. Não é preciso "
        "responder; acompanhe os próximos despachos.",
    ),
    _patente("2.7", "Republicação", _REPUBLICACAO_REABRE_PRAZO, requires_action=True),
    # Prazo condicional (só se houve procurador) e contado do depósito, não da publicação.
    _patente(
        "2.10",
        "Notificação de recebimento do pedido de patente ou certificado de adição",
        "O INPI recebeu o pedido e vai fazer a conferência inicial. Não é preciso responder. Atenção: se o "
        "depósito foi feito por procurador, a procuração precisa ser entregue em até 60 dias contados da data do "
        "depósito (não desta publicação), senão o pedido é arquivado de vez.",
        requires_action=True,
    ),
    # Publicação do Pedido (p. 6). Prazo de 36 meses contado do depósito, e só se o exame ainda não foi pedido.
    _patente(
        "3.1",
        "Pedido de Patente ou de Certificado de Adição de Invenção Publicado",
        "Acabou o sigilo e o INPI publicou o pedido. Atenção: se o exame ainda não foi pedido, ele precisa ser "
        "pago em até 36 meses contados do depósito (não desta publicação), senão o INPI arquiva o pedido. Se o "
        "exame já foi pedido, não é preciso fazer nada.",
        requires_action=True,
    ),
    _patente(
        "3.2",
        "Publicação do Pedido de Patente Antecipada",
        "O INPI publicou o pedido antes do fim do sigilo, a pedido do depositante. Atenção: se o exame ainda não "
        "foi pedido, ele precisa ser pago em até 36 meses contados do depósito (não desta publicação), senão o "
        "INPI arquiva o pedido. Se o exame já foi pedido, não é preciso fazer nada.",
        requires_action=True,
    ),
    _patente(
        "3.6",
        "Publicação do Pedido Arquivado Definitivamente",
        "O pedido foi arquivado de vez (por falta de procuração ou porque um pedido posterior reivindicou a "
        "prioridade dele) e o INPI publicou o conteúdo. O processo terminou no INPI. Não é preciso responder.",
    ),
    _patente(
        "3.7",
        "Publicação Anulada",
        "O INPI cancelou a publicação do pedido porque ela saiu por engano. Não é preciso responder.",
    ),
    _patente(
        "3.8",
        "Retificação",
        "O INPI corrigiu um erro na publicação do pedido. A correção não muda a data de publicação nem os "
        "prazos. Não é preciso responder.",
    ),
    # Pedido de Exame (p. 7)
    _patente(
        "4.3",
        "Desarquivamento - Art. 33 parágrafo único da LPI",
        "O pedido, que tinha sido arquivado por falta de pagamento do exame, voltou a andar. Não é preciso "
        "responder; acompanhe os próximos despachos.",
    ),
    _patente(
        "4.3.1",
        "Publicação Anulada",
        "O INPI cancelou a publicação do desarquivamento do pedido. O motivo está no complemento, na Busca de "
        "Processos. Se discordar, é possível apresentar recurso (GRU 214) em até 60 dias da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "4.3.2",
        "Republicação",
        "O INPI publicou de novo o desarquivamento do pedido, que tinha saído com erro. Não é preciso responder.",
    ),
    # Exigências Técnicas e Formais (pp. 8-10)
    _patente(
        "6.1",
        "Exigência Técnica - Art. 36 da LPI",
        "O INPI parou o exame e pediu ajustes no pedido. Veja o parecer na Busca de Processos e responda (GRU "
        "207) em até 90 dias corridos da publicação. Se ninguém responder no prazo, o pedido é arquivado de vez.",
        requires_action=True,
        deadline_days=90,
    ),
    _patente(
        "6.6",
        "Exigência Formal - Art. 34 da LPI",
        "O INPI parou o andamento e pediu documentos. Veja o parecer na Busca de Processos e responda (GRU 207) "
        "em até 60 dias corridos da publicação. Sem resposta no prazo, o pedido é arquivado.",
        requires_action=True,
        deadline_days=60,
    ),
    # Sem resposta, o INPI considera que não houve acesso ao patrimônio genético (não arquiva).
    _patente(
        "6.6.1",
        "Exigência Formal - Art. 38 (I) da Lei 13.123/2015",
        "O INPI pergunta se a invenção usou patrimônio genético ou conhecimento tradicional brasileiro. Responda "
        "em até 60 dias corridos da publicação. Sem resposta, o INPI considera que não houve esse uso.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "6.6.2",
        "Exigência formal - Acesso ao patrimônio genético - Art. 38 (I) da Lei 13.123/2015 e Art. 34 da LPI",
        "O INPI pede que o depositante informe se a invenção usou ou não patrimônio genético ou conhecimento "
        "tradicional brasileiro (GRU 264 se usou, GRU 273 se não usou), em até 60 dias corridos da publicação. "
        "Sem resposta, o pedido é arquivado.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "6.6.3",
        "Exigência formal - Listagem de sequências biológicas - Art. 34 da LPI",
        "O INPI pede a listagem de sequências biológicas no formato exigido. Veja o parecer e responda (GRU 207) "
        "em até 60 dias corridos da publicação. Sem resposta, o pedido é arquivado.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "6.7",
        "Outras Exigências - Art. 36 da LPI",
        "O INPI parou o exame por pendências e pediu documentos. Veja o parecer e responda (GRU 207) em até 90 "
        "dias corridos da publicação. Se ninguém responder no prazo, o pedido é arquivado de vez.",
        requires_action=True,
        deadline_days=90,
    ),
    _patente(
        "6.8",
        "Exigência Anulada",
        "O INPI cancelou uma exigência deste pedido porque ela foi indevida. Não é preciso responder.",
    ),
    _patente(
        "6.9",
        "Publicação Anulada",
        "O INPI cancelou a publicação de uma exigência porque ela saiu por engano. Não é preciso responder.",
    ),
    # Prazo condicional: 90 ou 60 dias, conforme o código da exigência republicada.
    _patente(
        "6.10",
        "Republicação - Arts. 34 e 36 da LPI",
        "O INPI publicou de novo uma exigência que tinha saído com erro, e o prazo volta a contar desta "
        "publicação: 90 dias corridos se a exigência original era 6.1, 6.7, 6.21, 6.22 ou 6.23, e 60 dias "
        "corridos nos outros casos. Sem resposta no prazo, o pedido é arquivado de vez.",
        requires_action=True,
    ),
    _patente(
        "6.20",
        "Exigência Pré-Exame - Art. 34 da LPI",
        "O INPI pediu argumentos sobre objeções, busca de anterioridades e resultados de exame em outros países. "
        "Veja o parecer e responda (GRU 206) em até 60 dias corridos da publicação. Sem resposta, o pedido é "
        "arquivado.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "6.21",
        "Exigência preliminar - Pedidos com buscas realizadas por outros Escritórios de Patentes - Art. 36 da LPI",
        "O INPI parou o exame e pediu documentos, com base em buscas feitas por outros escritórios de patentes. "
        "Veja o parecer e responda (GRU 207) em até 90 dias corridos da publicação. Sem resposta, o pedido é "
        "arquivado de vez.",
        requires_action=True,
        deadline_days=90,
    ),
    _patente(
        "6.22",
        "Exigência preliminar - Pedidos sem buscas realizadas por outros Escritórios de Patentes - Art. 36 da LPI",
        "O INPI parou o exame e pediu novas reivindicações e argumentos sobre as diferenças em relação aos "
        "documentos da busca. Responda (GRU 207) em até 90 dias corridos da publicação. Sem resposta, o pedido é "
        "arquivado de vez.",
        requires_action=True,
        deadline_days=90,
    ),
    _patente(
        "6.23",
        "Exigência preliminar - pedidos com buscas realizadas por outros Escritórios de Patentes - Art. 36 da LPI",
        "O INPI parou o exame e pediu que o pedido seja reapresentado (relatório, resumo, desenhos e "
        "reivindicações), com argumentos sobre as diferenças em relação à busca. Responda (GRU 207) em até 90 "
        "dias corridos da publicação. Sem resposta, o pedido é arquivado de vez.",
        requires_action=True,
        deadline_days=90,
    ),
    # Ciência de Parecer (pp. 11-12)
    _patente(
        "7.1",
        "Conhecimento de Parecer Técnico - Art. 36 da LPI",
        "O INPI emitiu um parecer técnico e espera a manifestação do depositante. Veja o parecer na Busca de "
        "Processos e responda (GRU 281) em até 90 dias corridos da publicação. Sem resposta, o INPI indefere "
        "(nega) o pedido.",
        requires_action=True,
        deadline_days=90,
    ),
    _patente("7.2", "Publicação Anulada", _PUBLICACAO_ANULADA),
    # Prazo condicional: depende do despacho republicado (90 dias se for o 7.1).
    _patente(
        "7.3",
        "Republicação por ter sido efetuada com incorreção",
        "O INPI publicou de novo um despacho que tinha saído com erro. Se ele pedia alguma providência, o prazo "
        "volta a contar desta publicação; se era o 7.1, são 90 dias corridos para responder (GRU 281). Confira "
        "no complemento qual foi o despacho.",
        requires_action=True,
    ),
    _patente(
        "7.4",
        "Ciência relacionada com o Art. 229-C da LPI",
        "O INPI enviou o pedido para a ANVISA analisar (regra já revogada). Não é preciso responder.",
    ),
    _patente(
        "7.5",
        "Notificação de Anuência relacionada com o Art. 229-C da LPI",
        "A ANVISA concordou com o pedido e o devolveu ao INPI (regra já revogada). Não é preciso responder.",
    ),
    _patente(
        "7.6",
        "Notificação de não Anuência relacionada com o Art. 229-C da LPI",
        "A ANVISA não concordou com o pedido e o devolveu ao INPI (regra já revogada). Veja o parecer na Busca "
        "de Processos. Não é preciso responder.",
    ),
    _patente(
        "7.7",
        "Notificação de Devolução do Pedido por não se Enquadrar no Art. 229-C da LPI",
        "A ANVISA entendeu que o pedido não precisava da análise dela e o devolveu ao INPI (regra já revogada). "
        "Não é preciso responder.",
    ),
    # Anuidade do Pedido (pp. 13-14)
    _patente(
        "8.5",
        "Exigência de Complementação e Saneamento de Retribuição Anual e Restauração - Art. 84 § 2º da LPI",
        "O INPI encontrou problemas no pagamento da anuidade ou no pedido de restauração. Veja o parecer e "
        "regularize (GRU 800 e GRU 207) em até 60 dias corridos da publicação. Sem resposta, o pedido é "
        "arquivado.",
        requires_action=True,
        deadline_days=60,
    ),
    # Prazo em meses.
    _patente(
        "8.6",
        "Arquivamento - Art. 86 da LPI",
        "O pedido foi arquivado por falta ou atraso no pagamento da anuidade. Ainda é possível pedir a "
        "restauração (GRU 208 e anuidade em atraso) em até 3 meses contados da publicação. " + _ANUIDADE_EM_MESES,
        requires_action=True,
    ),
    _patente(
        "8.7",
        "Restauração - Art. 87 da LPI",
        "O INPI aceitou a restauração e o pedido voltou a andar. Não é preciso responder.",
    ),
    _patente("8.8", "Despacho Anulado", _DESPACHO_ANULADO),
    _patente("8.9", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("8.10", "Republicação", _REPUBLICACAO_REABRE_PRAZO, requires_action=True),
    _patente(
        "8.11",
        "Manutenção do Arquivamento",
        "O pedido continua arquivado de vez porque a restauração não foi pedida no prazo. O processo terminou no "
        "INPI. Não é preciso responder.",
    ),
    _patente(
        "8.12",
        "Arquivamento Definitivo - Arts. 84, 86 e 212 § 2º da LPI",
        "O pedido foi arquivado de vez por falta de pagamento de mais de uma anuidade (regra já revogada). Não é "
        "preciso responder.",
    ),
    # Decisão (pp. 15-16)
    _patente(
        "9.1",
        "Deferimento - Art. 38 da LPI e Resolução 72/2013",
        "Boa notícia: o INPI aprovou o pedido. A carta-patente será expedida sem custo. Não é preciso responder.",
    ),
    _patente(
        "9.1.1",
        "Decisão Anulada",
        "O INPI cancelou a aprovação (deferimento) do pedido. Veja o motivo no parecer. Se discordar, é possível "
        "apresentar recurso (GRU 214) em até 60 dias corridos da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "9.1.2",
        "Publicação Anulada",
        "O INPI cancelou a publicação da aprovação (deferimento) do pedido. Veja o motivo no parecer. Se "
        "discordar, é possível apresentar recurso (GRU 214) em até 60 dias corridos da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "9.1.3",
        "Republicação - Art. 38 da LPI e Resolução 72/2013",
        "O INPI publicou de novo a aprovação do pedido, que tinha saído com erro. A carta-patente será expedida "
        "sem custo. Não é preciso responder.",
    ),
    _patente(
        "9.1.4",
        "Retificação",
        "O INPI corrigiu um erro na publicação da aprovação do pedido. A data da aprovação não muda. Não é "
        "preciso responder.",
    ),
    _patente(
        "9.2",
        "Indeferimento - Art. 76 §4° e Art. 212 da LPI",
        "O INPI negou (indeferiu) o pedido. Veja os motivos no parecer técnico. Se discordar, é possível "
        "apresentar recurso (GRU 214) em até 60 dias corridos da publicação. Sem recurso, a negativa fica "
        "definitiva.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "9.2.1",
        "Decisão Anulada",
        "O INPI cancelou a decisão que tinha negado o pedido. Veja o motivo no parecer. Não é preciso responder; "
        "acompanhe os próximos despachos.",
    ),
    _patente(
        "9.2.2",
        "Publicação Anulada",
        "O INPI cancelou a publicação da negativa (indeferimento) do pedido. Veja o motivo no parecer e "
        "acompanhe os próximos despachos.",
    ),
    _patente(
        "9.2.3",
        "Republicação",
        "O INPI publicou de novo a negativa (indeferimento) do pedido, que tinha saído com erro. Se discordar, é "
        "possível apresentar recurso (GRU 214) em até 60 dias corridos desta nova publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "9.2.4",
        "Manutenção do Indeferimento - Art. 212 da LPI",
        "O pedido continua negado porque não houve recurso no prazo. Não é preciso responder.",
    ),
    _patente(
        "9.2.4.1",
        "Publicação Anulada",
        "O INPI cancelou a publicação que mantinha a negativa do pedido. Ainda é possível apresentar recurso "
        "(GRU 214) em até 60 dias corridos da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    # Desistência (p. 17)
    _patente(
        "10.1",
        "Desistência Homologada",
        "O INPI aceitou a desistência do pedido. O processo terminou no INPI. Não é preciso responder.",
    ),
    _patente(
        "10.5",
        "Desistência Não Homologada",
        "O INPI não aceitou a desistência do pedido, que continua em andamento; o motivo está no complemento. Se "
        "discordar, é possível apresentar recurso (GRU 214) em até 60 dias da publicação.",
    ),
    _patente("10.6", "Despacho Anulado", _DESPACHO_ANULADO),
    _patente("10.7", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("10.8", "Republicação", _REPUBLICACAO_REABRE_PRAZO, requires_action=True),
    _patente(
        "10.9",
        "Retirada Homologada - Art. 29 § 1º da LPI",
        "O INPI aceitou a retirada do pedido. O processo terminou no INPI. Não é preciso responder.",
    ),
    _patente(
        "10.9.1",
        "Retirada não Homologada - Art. 29 § 1º da LPI",
        "O INPI não aceitou a retirada do pedido, que continua em andamento; veja o complemento. Se discordar, é "
        "possível apresentar recurso (GRU 214) em até 60 dias da publicação.",
    ),
    _patente(
        "10.10",
        "Desistência de petição Homologada",
        "O INPI aceitou a desistência de uma petição deste pedido. Não é preciso responder.",
    ),
    _patente(
        "10.11",
        "Desistência de petição Não Homologada",
        "O INPI não aceitou a desistência de uma petição deste pedido. Confira o complemento.",
    ),
    # Arquivamento (pp. 18-20)
    _patente(
        "11.1",
        "Arquivamento - Artigos 33, 216 e 217 da Lei da Propriedade Industrial (LPI), Resolução 94/2014 e "
        "Portaria 302/2020",
        "O pedido foi arquivado porque o exame não foi pago no prazo. Ainda dá para desarquivar: pague a GRU 209 "
        "e a GRU do pedido de exame em até 60 dias corridos da publicação. Sem isso, o arquivamento fica "
        "definitivo.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "11.1.1",
        "Arquivamento definitivo - Artigo 33 da Lei da Propriedade Industrial (LPI)",
        "O pedido foi arquivado de vez porque o desarquivamento não foi pedido no prazo. O processo terminou no "
        "INPI.",
    ),
    _patente(
        "11.2",
        "Arquivamento - Artigo 36, parágrafo §1°, da Lei da Propriedade Industrial (LPI)",
        "O pedido foi arquivado de vez porque a exigência não foi respondida no prazo. O processo terminou no "
        "INPI.",
    ),
    _patente(
        "11.4",
        "Arquivamento - Artigo 38, parágrafo §2°, da Lei da Propriedade Industrial (LPI)",
        "O pedido foi arquivado de vez porque a taxa de expedição da carta-patente não foi paga no prazo.",
    ),
    _patente(
        "11.5",
        "Arquivamento - Artigo 34 da Lei da Propriedade Industrial (LPI)",
        "O pedido foi arquivado porque a exigência não foi respondida no prazo. Se discordar, é possível "
        "apresentar recurso (GRU 214) em até 60 dias corridos da publicação. Sem recurso, o arquivamento é "
        "mantido.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "11.6",
        "Arquivamento do Pedido - Artigo 216, parágrafo §2°, da Lei da Propriedade Industrial (LPI)",
        "O pedido foi arquivado de vez porque a procuração não foi entregue no prazo. O processo terminou no "
        "INPI.",
    ),
    _patente(
        "11.6.1",
        "Arquivamento da Petição - Artigo 216, parágrafo §2º, da Lei da Propriedade Industrial (LPI)",
        "Uma petição deste pedido foi arquivada porque a procuração não foi entregue no prazo. Se discordar, é "
        "possível apresentar recurso (GRU 214) em até 60 dias da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "11.11",
        "Arquivamento - Artigo 17, parágrafo §2º, da Lei da Propriedade Industrial (LPI)",
        "O pedido foi arquivado de vez porque foi depositado um pedido posterior que reivindica a prioridade "
        "dele. O número do pedido posterior está no complemento; acompanhe aquele pedido.",
    ),
    _patente(
        "11.12",
        "Arquivamento - Artigo 26 parágrafo único da Lei da Propriedade Industrial (LPI)",
        "O pedido foi arquivado porque a divisão foi pedida fora do prazo. Se discordar, é possível apresentar "
        "recurso (GRU 214) em até 60 dias corridos da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "11.13",
        "Despacho Anulado",
        "O INPI cancelou o arquivamento do pedido porque ele foi indevido. Não é preciso responder; acompanhe os "
        "próximos despachos.",
    ),
    _patente(
        "11.14",
        "Publicação Anulada",
        "O INPI cancelou a publicação do arquivamento do pedido porque ela foi indevida. Não é preciso "
        "responder; acompanhe os próximos despachos.",
    ),
    # Prazo condicional: o recurso depende do despacho republicado.
    _patente(
        "11.15",
        "Republicação",
        "O INPI publicou de novo um despacho que tinha saído com erro. Dependendo do despacho, é possível "
        "apresentar recurso (GRU 214) em até 60 dias desta publicação. Confira o complemento.",
        requires_action=True,
    ),
    _patente(
        "11.17",
        "Arquivamento do pedido de Certificado de Adição de Invenção - Artigos 76 e 77 da Lei da Propriedade "
        "Industrial (LPI)",
        "O pedido de certificado de adição foi arquivado porque não existe patente principal à qual ele se "
        "ligue. Para transformá-lo em pedido de patente, é preciso apresentar recurso (GRU 214) em até 60 dias "
        "corridos da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "11.18",
        "Arquivamento definitivo por não anuência relacionada com o Artigo 229-C da Lei da Propriedade "
        "Industrial (LPI)",
        "O pedido foi arquivado de vez porque a ANVISA não deu a anuência (regra já revogada).",
    ),
    _patente(
        "11.20",
        "Manutenção do arquivamento - Artigo 220 da Lei da Propriedade Industrial (LPI)",
        "O pedido continua arquivado de vez porque não houve recurso no prazo.",
    ),
    _patente(
        "11.21",
        "Arquivamento definitivo - Apresentação de um pedido posterior depositado via Tratado de Cooperação em "
        "matéria de Patentes (PCT)",
        "O pedido foi arquivado de vez porque um pedido internacional (PCT) posterior, que reivindica a "
        "prioridade dele, entrou no Brasil. O número desse pedido está no complemento.",
    ),
    # Sem prazo: os documentos podem ser apresentados a qualquer tempo.
    _patente(
        "11.34",
        "Arquivamento",
        "O pedido foi arquivado porque não foi possível restaurar ou reconstituir o processo. Os documentos "
        "pedidos no despacho 15.34 podem ser enviados a qualquer momento (GRU 259), sem prazo.",
        requires_action=True,
    ),
    _patente(
        "11.34.1",
        "Desarquivamento",
        "O pedido foi desarquivado depois que o processo foi restaurado ou reconstituído. Não é preciso "
        "responder.",
    ),
    # Recurso (p. 21). O prazo de 60 dias é para terceiros se manifestarem, não para o titular.
    _patente(
        "12.2",
        "Recurso contra o Indeferimento - Artigos 212 e 213 da Lei da Propriedade Industrial (LPI)",
        "O INPI registrou o recurso contra a negativa do pedido. Outros interessados têm 60 dias para se "
        "manifestar contra o recurso. Não é preciso fazer nada agora; aguarde a decisão.",
    ),
    _patente(
        "12.3",
        "Recurso contra o Arquivamento - Artigos 212 e 213 da Lei da Propriedade Industrial (LPI)",
        "O INPI registrou o recurso contra o arquivamento. Outros interessados têm 60 dias para se manifestar "
        "contra o recurso. Não é preciso fazer nada agora; aguarde a decisão.",
    ),
    _patente(
        "12.6",
        "Outros Recursos - Artigos 212 e 213 da Lei da Propriedade Industrial (LPI)",
        "O INPI registrou um recurso contra uma decisão sobre este processo. Interessados têm 60 dias para se "
        "manifestar contra o recurso. Confira no complemento quem recorreu e de quê.",
    ),
    _patente("12.7", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("12.8", "Republicação", _REPUBLICACAO_REABRE_PRAZO, requires_action=True),
    # Outros Referentes a Despachos (pp. 22-24)
    _patente("15.7", "Petição não Conhecida", _PETICAO_NAO_CONHECIDA),
    _patente(
        "15.8",
        "Petição Sustada",
        "O INPI suspendeu a análise de uma petição deste pedido. Confira o motivo no complemento do despacho.",
    ),
    _patente(
        "15.9",
        "Perda de Prioridade",
        "O pedido perdeu a prioridade que tinha reivindicado. Confira o motivo no complemento do despacho.",
    ),
    _patente(
        "15.10",
        "Mudança de Natureza",
        "O INPI mudou a natureza do pedido e, com isso, o número do pedido mudou.",
    ),
    _patente(
        "15.11",
        "Alteração de Classificação",
        "O INPI mudou a classificação técnica do pedido para adequá-la melhor. Não é preciso fazer nada.",
    ),
    _patente(
        "15.12",
        "Renumeração",
        "O INPI corrigiu o número do pedido, que tinha sido dado por engano. Não é preciso fazer nada.",
    ),
    _patente(
        "15.14",
        "Notificação de Decisão Judicial",
        "O INPI comunica uma decisão da Justiça sobre este pedido. Confira o complemento.",
    ),
    _patente(
        "15.15",
        "Requerimento de entrada na fase nacional não processado (Pedido PCT retirado antes da publicação)",
        "O pedido de entrada no Brasil não vai andar porque o pedido internacional foi retirado antes de ser "
        "publicado.",
    ),
    _patente(
        "15.16",
        "Requerimento de entrada na fase nacional não processado (Número do pedido PCT inexistente)",
        "O pedido de entrada no Brasil não vai andar porque o número do pedido internacional informado não "
        "existe na base da OMPI.",
    ),
    _patente(
        "15.21",
        "Documentação arquivada e depósito não efetuado",
        "Os documentos foram arquivados e o depósito foi considerado não feito. O conteúdo não será divulgado.",
    ),
    _patente("15.22", "Devolução de Prazo Concedida", _DEVOLUCAO_DE_PRAZO, requires_action=True),
    _patente(
        "15.22.1",
        "Devolução de Prazo Negada",
        "O INPI negou a devolução de prazo pedida. Se discordar, é possível apresentar recurso em até 60 dias da "
        "publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "15.22.2",
        "Devolução de Prazo por falha de Sistema",
        "O pedido foi incluído numa devolução de prazo por falha de sistema já decidida pelo INPI. Confira o "
        "comunicado na RPI ou no site do INPI.",
    ),
    _patente("15.23", "Pedido “SUB JUDICE”", "Existe uma ação na Justiça sobre este pedido."),
    _patente(
        "15.25.1",
        "Notificação de requerimento de anúncio de pedido",
        "Foi pedido o anúncio deste pedido na Vitrine de PI do INPI. A publicação depende do cumprimento das "
        "regras.",
    ),
    # Prazo de 60 dias sem início definido; afeta só o anúncio, não o pedido.
    _patente(
        "15.25.2",
        "Exigência formal para anúncio na Vitrine de PI de pedido",
        "O pedido de anúncio na Vitrine de PI tem problemas formais, que podem ser corrigidos em 60 dias (GRU "
        "206). Isso afeta só o anúncio, não o pedido de patente.",
    ),
    _patente(
        "15.25.3",
        "Anúncio de pedido admitido",
        "O anúncio do pedido na Vitrine de PI foi aceito.",
    ),
    _patente(
        "15.25.4",
        "Anúncio de pedido não admitido",
        "O anúncio do pedido na Vitrine de PI não foi aceito. É possível fazer um novo pedido de anúncio com a "
        "documentação.",
    ),
    _patente("15.30", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("15.31", "Despacho Anulado", _DESPACHO_ANULADO),
    _patente("15.32", "Decisão Anulada", _DECISAO_ANULADA),
    _patente("15.33", "Republicação", _REPUBLICACAO),
    _patente(
        "15.34",
        "Restauração/Reconstituição dos Autos do Pedido",
        _RESTAURACAO_DOS_AUTOS,
        requires_action=True,
    ),
    _patente(
        "15.34.1",
        "Pedido Restaurado ou Reconstituído",
        "O processo do pedido foi restaurado. Não é preciso fazer nada.",
    ),
    _patente(
        "15.34.2",
        "Pedido Não Restaurado ou Não Reconstituído",
        _DOCUMENTOS_A_QUALQUER_TEMPO,
        requires_action=True,
    ),
    _patente(
        "15.34.3",
        "Documentação incompleta",
        "A restauração não foi feita porque a documentação estava incompleta. Os documentos que faltam podem ser "
        "enviados a qualquer momento (GRU 259), sem prazo.",
        requires_action=True,
    ),
    _patente(
        "15.35",
        "Atualização de informações no portal",
        "O INPI atualizou dados do pedido no portal. Os prazos não mudam e não é preciso fazer nada.",
    ),
    _patente(
        "15.50",
        "Notificação de depósito de um pedido dividido",
        "Foi depositada uma divisão deste pedido; os dados estão no complemento. Os prazos não mudam e não é "
        "preciso fazer nada.",
    ),
    # Concessão de Patente e Certificado de Adição de Invenção (p. 25)
    _patente(
        "16.1",
        "Concessão de Patente ou Certificado de Adição de Invenção",
        "Boa notícia: a patente foi concedida e a carta-patente foi expedida. Nos próximos 6 meses, qualquer "
        "pessoa pode pedir ao INPI a nulidade administrativa da patente.",
    ),
    _patente(
        "16.2",
        "Publicação Anulada",
        "O INPI cancelou a publicação da concessão porque ela saiu por engano.",
    ),
    _patente(
        "16.3",
        "Retificação",
        "O INPI corrigiu um erro na publicação da concessão. A data da concessão e os prazos não mudam.",
    ),
    _patente(
        "16.4",
        "Concessão Anulada",
        "O INPI anulou a concessão da patente porque ela foi indevida. Confira o motivo no complemento.",
    ),
    # Nulidade Administrativa (p. 26)
    _patente(
        "17.1",
        "Notificação de Interposição de Nulidade Administrativa",
        "Alguém pediu ao INPI que anule a patente. O titular pode se defender (contestação) em até 60 dias da "
        "publicação. A cópia do pedido de nulidade está na Busca de Processos.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "17.2",
        "Publicação Anulada",
        "O INPI cancelou o aviso de abertura do processo de nulidade porque ele saiu por engano.",
    ),
    _patente(
        "17.3",
        "Republicação",
        "O INPI publicou de novo o aviso de abertura do processo de nulidade, que tinha saído com erro. Confira "
        "o complemento.",
    ),
    # Caducidade (p. 27)
    _patente(
        "18.1",
        "Notificação de Pedido de Caducidade",
        "Foi aberto um processo para declarar a caducidade da patente por falta de uso (exploração). O titular "
        "pode se manifestar em até 60 dias da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "18.3",
        "Caducidade Deferida",
        "O INPI declarou a caducidade da patente por falta de uso. Se discordar, o titular pode apresentar "
        "recurso em até 60 dias da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "18.4",
        "Caducidade Indeferida",
        "O INPI negou o pedido de caducidade e a patente continua valendo. Quem pediu a caducidade pode recorrer "
        "em até 60 dias.",
    ),
    _patente(
        "18.5",
        "Recurso contra o Deferimento da Caducidade",
        "Foi apresentado recurso contra a decisão que declarou a caducidade da patente. Aguarde a decisão.",
    ),
    _patente(
        "18.6",
        "Recurso contra o Indeferimento da Caducidade",
        "Foi apresentado recurso contra a decisão que negou a caducidade da patente. Aguarde a decisão.",
    ),
    # A exigência é para quem pediu a caducidade, não para o titular.
    _patente(
        "18.7",
        "Exigência para caducidade",
        "O pedido de caducidade tem problemas formais e quem o apresentou tem 60 dias para corrigir, senão ele é "
        "negado.",
    ),
    _patente(
        "18.8",
        "Petição de caducidade não conhecida",
        "O INPI não aceitou analisar a petição de caducidade; os motivos estão no despacho.",
    ),
    _patente(
        "18.10",
        "Desistência de Caducidade",
        "Quem pediu a caducidade desistiu, mas o INPI pode continuar o processo.",
    ),
    _patente(
        "18.11",
        "Decisão Anulada",
        "O INPI anulou a decisão sobre a caducidade porque ela foi indevida. Confira o complemento.",
    ),
    _patente("18.12", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("18.13", "Republicação", _REPUBLICACAO),
    # Notificação de Decisão Judicial (p. 28)
    _patente(
        "19.1",
        "Notificação de Decisão Judicial",
        "O INPI comunica uma decisão da Justiça sobre a patente. Confira o complemento.",
    ),
    _patente(
        "19.2",
        "Publicação Anulada",
        "O INPI cancelou a publicação de uma decisão judicial porque ela saiu por engano.",
    ),
    _patente(
        "19.3",
        "Retificação",
        "O INPI corrigiu um erro na publicação de uma decisão judicial.",
    ),
    # Extinção de Patente e Certificado de Adição de Invenção (p. 29)
    _patente(
        "21.1",
        "Extinção - Art. 78 inciso I da LPI",
        "A patente terminou porque acabou o prazo de validade (vigência).",
    ),
    _patente(
        "21.2",
        "Extinção - Art 78 inciso II da LPI",
        "A patente terminou porque o titular renunciou a ela.",
    ),
    # Prazo em meses.
    _patente(
        "21.6",
        "Extinção - Art. 86 da LPI",
        "A patente foi extinta por falta ou atraso no pagamento da anuidade. Ainda é possível pedir a "
        "restauração (GRU 208 e pagamentos em atraso) em até 3 meses da publicação. " + _ANUIDADE_EM_MESES,
        requires_action=True,
    ),
    _patente(
        "21.7",
        "Extinção - Art. 78 inciso V da LPI",
        "A patente foi extinta porque o titular não apresentou a comprovação pedida pelo INPI (Art. 217 da LPI).",
    ),
    _patente(
        "21.8",
        "Despacho Anulado",
        "O INPI anulou o despacho de extinção da patente porque ele foi indevido.",
    ),
    _patente("21.9", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("21.10", "Republicação", _REPUBLICACAO),
    # Outros Referentes a Patentes/Certificados de Adição de Invenção (pp. 30-31)
    _patente(
        "22.2",
        "Petição Não Conhecida",
        "O INPI não aceitou analisar uma petição sobre a patente (Arts. 218 ou 219 da LPI).",
    ),
    _patente(
        "22.3",
        "Petição Sustada",
        "O INPI suspendeu a análise de uma petição até que sejam tomadas providências. Confira o complemento.",
    ),
    _patente(
        "22.4",
        "Pedido de Licença Compulsória Para Exploração de Patente",
        "Alguém pediu licença compulsória para explorar a patente. O titular pode se manifestar em até 60 dias "
        "da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "22.5",
        "Exigências Diversas",
        "O INPI fez uma exigência sobre a patente, que precisa ser cumprida em até 60 dias da publicação. Se ela "
        "não estiver no despacho, o parecer está na Busca de Processos.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "22.6.1",
        "Notificação de requerimento de anúncio de patente",
        "Foi pedido o anúncio desta patente na Vitrine de PI do INPI. A publicação depende do cumprimento das "
        "regras.",
    ),
    # Prazo de 60 dias sem início definido; afeta só o anúncio, não a patente.
    _patente(
        "22.6.2",
        "Exigência formal para anúncio na Vitrine de PI de Patentes",
        "O pedido de anúncio na Vitrine de PI tem problemas formais, que podem ser corrigidos em 60 dias (GRU "
        "206). Isso afeta só o anúncio, não a patente.",
    ),
    _patente(
        "22.6.3",
        "Anúncio de patente admitido",
        "O anúncio da patente na Vitrine de PI foi aceito.",
    ),
    _patente(
        "22.6.4",
        "Anúncio de patente não admitido",
        "O anúncio da patente na Vitrine de PI não foi aceito. É possível fazer um novo pedido de anúncio com a "
        "documentação.",
    ),
    _patente("22.11", "Devolução de Prazo", _DEVOLUCAO_DE_PRAZO, requires_action=True),
    _patente(
        "22.12",
        "Oferta de Licença de Patente",
        "Foi publicada a oferta de licença da patente feita pelo titular. Interessados podem pedir as condições.",
    ),
    _patente(
        "22.13",
        "Desistência da Oferta de Licença",
        "O titular desistiu da oferta de licença da patente.",
    ),
    _patente(
        "22.14",
        "Arquivamento da Petição – Art. 216 §2º da LPI",
        "Uma petição sobre a patente foi arquivada porque a procuração não foi entregue em 60 dias. É possível "
        "apresentar recurso em até 60 dias da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente("22.15", "Patente “SUB JUDICE”", "Existe uma ação na Justiça sobre esta patente."),
    _patente("22.20", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("22.21", "Despacho Anulado", _DESPACHO_ANULADO),
    _patente("22.22", "Decisão Anulada", _DECISAO_ANULADA),
    _patente("22.23", "Republicação", _REPUBLICACAO),
    _patente(
        "22.25",
        "Desistência de petição de patente Homologada",
        "O INPI aceitou a desistência de uma petição sobre a patente.",
    ),
    _patente(
        "22.26",
        "Desistência de petição de patente Não Homologada",
        "O INPI não aceitou a desistência de uma petição sobre a patente.",
    ),
    _patente(
        "22.34",
        "Restauração/Reconstituição dos Autos da Patente",
        _RESTAURACAO_DOS_AUTOS,
        requires_action=True,
    ),
    _patente(
        "22.34.1",
        "Patente Restaurada ou Reconstituída",
        "O processo da patente foi restaurado. Não é preciso fazer nada.",
    ),
    _patente(
        "22.34.2",
        "Patente Não Restaurada ou Não Reconstituída",
        _DOCUMENTOS_A_QUALQUER_TEMPO,
        requires_action=True,
    ),
    _patente(
        "22.34.3",
        "Documentação incompleta",
        "A restauração não foi feita porque a documentação estava incompleta. Os documentos que faltam podem ser "
        "enviados a qualquer momento (GRU 259), sem prazo.",
        requires_action=True,
    ),
    # Processamento de Pedidos Segundo Artigos 230 e 231 da Lei 9279/96 (pp. 32-33)
    _patente(
        "23.1",
        "Notificação de Pedido Depositado",
        "O INPI comunica o depósito do pedido (regime especial dos Arts. 230 e 231 da LPI).",
    ),
    _patente(
        "23.1.1",
        "Notificação de Depósito de Pedido Dividido",
        "Foi depositada uma divisão do pedido, com a mesma data de depósito e na mesma fase do original.",
    ),
    _patente(
        "23.2",
        "Exigência",
        "O INPI parou o andamento do pedido até que a exigência seja cumprida, em até 90 dias da publicação.",
        requires_action=True,
        deadline_days=90,
    ),
    _patente(
        "23.3",
        "Publicação do Pedido para Manifestação de Terceiros",
        "O pedido foi publicado e qualquer interessado tem 90 dias para se manifestar sobre ele.",
    ),
    _patente(
        "23.4",
        "Notificação para Contestação do Depositante",
        "O INPI pede que o depositante apresente contestação. " + _PRAZO_SEM_INICIO,
        requires_action=True,
    ),
    _patente("23.6", "Arquivamento", "O pedido foi arquivado. Confira o motivo no complemento."),
    _patente("23.7", "Denegação do Pedido", "O pedido foi negado. Confira o motivo no complemento."),
    _patente("23.8", "Recurso", "Foi registrado um recurso neste pedido. Confira o complemento."),
    _patente("23.9", "Expedição da Patente", "A patente foi expedida."),
    _patente("23.10", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("23.11", "Republicação", _REPUBLICACAO),
    _patente("23.12", "Retificação", _RETIFICACAO),
    _patente(
        "23.13",
        "Deferimento",
        "O pedido foi aprovado. A carta-patente será expedida sem custo.",
    ),
    _patente("23.14", "Decisão Anulada", _DECISAO_ANULADA),
    _patente("23.15", "Expedição Anulada", "A expedição da patente foi anulada. Confira o complemento."),
    _patente("23.16", "Outros", "Outro tipo de despacho sobre este pedido. Confira o complemento."),
    _patente(
        "23.17",
        "Ciência Relacionada com o Art. 229 da LPI",
        "O exame técnico aprovou o pedido, mas a decisão final depende da anuência prevista no Art. 229 da LPI.",
    ),
    _patente(
        "23.18",
        "Notificação de Interposição de Nulidade Administrativa",
        "Alguém pediu ao INPI que anule a patente. O titular pode se defender (contestação) em até 60 dias da "
        "publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "23.19",
        "Extinção – Art. 78 da LPI",
        "A patente (pipeline) terminou porque acabou o prazo de validade.",
    ),
    # Anuidade de Patente (p. 34)
    _patente(
        "24.1",
        "Exigência de Comprovação de Anuidade",
        "O INPI pede a comprovação do pagamento da anuidade. " + _PRAZO_SEM_INICIO,
        requires_action=True,
    ),
    # Prazo de 60 dias sem início definido.
    _patente(
        "24.2",
        "Exigência de Complementação da Retribuição Anual",
        "O titular precisa completar o pagamento da anuidade; sem isso, em 60 dias a patente é extinta. A "
        "tabela não diz a partir de quando o prazo conta; confira o complemento.",
        requires_action=True,
    ),
    _patente(
        "24.3",
        "Notificação da extinção da patente para fins da restauração nos termos do art.87 da LPI.",
        "A patente foi extinta, mas ainda pode ser restaurada (Art. 87 da LPI). " + _PRAZO_SEM_INICIO,
        requires_action=True,
    ),
    _patente("24.4", "Restauração", "O INPI comunica a restauração da patente."),
    _patente("24.5", "Despacho Anulado", _DESPACHO_ANULADO),
    _patente("24.6", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("24.7", "Republicação", _REPUBLICACAO),
    _patente(
        "24.8",
        "Extinção Definitiva - Art. 78 inciso IV da LPI",
        "A patente foi extinta de vez por falta de pagamento de mais de uma anuidade, sem possibilidade de "
        "restauração.",
    ),
    _patente(
        "24.10",
        "Manutenção da Extinção - Art. 78 inciso IV da LPI",
        "A extinção da patente foi mantida.",
    ),
    # Anotação de Alteração de nome e/ou sede, de Transferência e de Limitação ou Ônus (pp. 35-36).
    # Pedido do próprio titular negado ou em exigência: exige ação.
    _patente(
        "25.1",
        "Transferência Deferida",
        "O INPI aceitou a transferência de titularidade pedida. Interessados podem recorrer em até 60 dias.",
    ),
    _patente(
        "25.2",
        "Transferência Indeferida",
        "O INPI negou a transferência de titularidade pedida. Se discordar, é possível recorrer em até 60 dias "
        "da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "25.3",
        "Transferência em Exigência",
        "O INPI pediu ajustes no pedido de transferência de titularidade. Cumpra a exigência em até 60 dias da "
        "publicação, senão a transferência é negada.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "25.4",
        "Alteração de Nome Deferida",
        "O INPI aceitou a alteração de nome pedida. Interessados podem recorrer em até 60 dias.",
    ),
    _patente(
        "25.5",
        "Alteração de Nome Indeferida",
        "O INPI negou a alteração de nome pedida. Se discordar, é possível recorrer em até 60 dias da "
        "publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "25.6",
        "Alteração de Nome em Exigência",
        "O INPI pediu ajustes no pedido de alteração de nome. Cumpra a exigência em até 60 dias da publicação, "
        "senão a alteração é negada.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "25.7",
        "Alteração de Sede Deferida",
        "O INPI aceitou a alteração de sede pedida. Interessados podem recorrer em até 60 dias.",
    ),
    _patente(
        "25.8",
        "Alteração de Sede Indeferida",
        "O INPI negou a alteração de sede pedida. Se discordar, é possível recorrer em até 60 dias da "
        "publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente(
        "25.9",
        "Alteração de Sede em Exigência",
        "O INPI pediu ajustes no pedido de alteração de sede. Cumpra a exigência em até 60 dias da publicação, "
        "senão a alteração é negada.",
        requires_action=True,
        deadline_days=60,
    ),
    _patente("25.10", "Despacho Anulado", _DESPACHO_ANULADO),
    _patente("25.11", "Republicação", _REPUBLICACAO),
    _patente("25.12", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente(
        "25.13",
        "Anotação de Limitação ou Ônus",
        "O INPI registrou uma limitação ou ônus sobre o pedido ou a patente, conforme o complemento.",
    ),
    # Opinião Preliminar sobre a Patenteabilidade – Programa Piloto (p. 37)
    _patente(
        "26.1",
        "Pedido Apto",
        "O pedido pode participar do programa piloto de opinião preliminar sobre a patenteabilidade.",
    ),
    _patente(
        "26.2",
        "Pedido Irregular",
        "O pedido não pode participar do programa piloto de opinião preliminar sobre a patenteabilidade.",
    ),
    _patente(
        "26.3",
        "Pedido Excedente",
        "O pedido passou do limite de vagas do programa piloto de opinião preliminar sobre a patenteabilidade.",
    ),
    _patente(
        "26.4",
        "Opinião Preliminar sobre a Patenteabilidade",
        "O INPI enviou a opinião preliminar sobre a patenteabilidade do pedido. Confira o documento.",
    ),
    _patente("26.5", "Republicação", _REPUBLICACAO),
    _patente("26.6", "Retificação", _RETIFICACAO_SEM_MUDAR_PRAZO),
    _patente("26.7", "Publicação anulada", _PUBLICACAO_ANULADA),
    # Códigos para Trâmite Prioritário (pp. 38-40). Afetam só a velocidade do exame, não o pedido.
    _patente(
        "28.10",
        "Notificação de requerimento de trâmite prioritário",
        "Foi pedido trâmite prioritário (análise mais rápida) deste pedido. A aceitação depende das regras. Não "
        "é preciso fazer nada agora.",
    ),
    _patente(
        "28.10.1",
        "Notificação de requerimento de trâmite prioritário de depositante idoso",
        _tramite_prioritario("depositante idoso"),
    ),
    _patente(
        "28.10.2",
        "Notificação de requerimento de trâmite prioritário de depositante portador de deficiência física ou "
        "mental",
        _tramite_prioritario("depositante com deficiência física ou mental"),
    ),
    _patente(
        "28.10.3",
        "Notificação de requerimento de trâmite prioritário de depositante portador de doença grave",
        _tramite_prioritario("depositante com doença grave"),
    ),
    _patente(
        "28.10.4",
        "Notificação de requerimento de trâmite prioritário de depositante MEI, ME ou EPP",
        _tramite_prioritario("depositante MEI, ME ou EPP"),
    ),
    _patente(
        "28.10.5",
        "Notificação de requerimento de trâmite prioritário de depositante ICT",
        _tramite_prioritario("depositante ICT (instituição científica e tecnológica)"),
    ),
    _patente(
        "28.10.6",
        "Notificação de requerimento de trâmite prioritário de depositante Startup",
        _tramite_prioritario("depositante startup"),
    ),
    _patente(
        "28.10.11",
        "Notificação de requerimento de trâmite prioritário de tecnologia verde",
        _tramite_prioritario("tecnologia verde"),
    ),
    _patente(
        "28.10.12",
        "Notificação de requerimento de trâmite prioritário de tecnologia para tratamento de saúde",
        _tramite_prioritario("tecnologia para tratamento de saúde"),
    ),
    _patente(
        "28.10.13",
        "Notificação de requerimento de trâmite prioritário de tecnologia solicitada pelo Ministério da Saúde",
        _tramite_prioritario("tecnologia solicitada pelo Ministério da Saúde"),
    ),
    _patente(
        "28.10.14",
        "Notificação de requerimento de trâmite prioritário para tecnologia para Copa do Mundo",
        _tramite_prioritario("tecnologia para a Copa do Mundo"),
    ),
    _patente(
        "28.10.21",
        "Notificação de requerimento de trâmite prioritário de depositante acusa de contrafação",
        _tramite_prioritario("o depositante acusa alguém de contrafação (cópia)"),
    ),
    _patente(
        "28.10.22",
        "Notificação de requerimento de trâmite prioritário de terceiro acusado de contrafação",
        _tramite_prioritario("terceiro acusado de contrafação (cópia)"),
    ),
    _patente(
        "28.10.23",
        "Notificação de requerimento de trâmite prioritário de usuário anterior de tecnologia",
        _tramite_prioritario("usuário anterior da tecnologia"),
    ),
    _patente(
        "28.10.24",
        "Notificação de requerimento de trâmite prioritário para liberação de recurso financeiro",
        _tramite_prioritario("liberação de recurso financeiro"),
    ),
    _patente(
        "28.10.25",
        "Notificação de requerimento de trâmite prioritário de tecnologia resultante de financiamento público",
        _tramite_prioritario("tecnologia resultante de financiamento público"),
    ),
    _patente(
        "28.10.26",
        "Notificação de requerimento de trâmite prioritário de tecnologia disponibilizada no mercado",
        _tramite_prioritario("tecnologia já disponível no mercado"),
    ),
    _patente(
        "28.10.31",
        "Notificação de requerimento de trâmite prioritário de família de patente iniciada no Brasil",
        _tramite_prioritario("família de patente iniciada no Brasil"),
    ),
    _patente(
        "28.10.32",
        "Notificação de requerimento de trâmite prioritário de PPH",
        _tramite_prioritario("PPH (acordo de cooperação entre escritórios de patentes)"),
    ),
    _patente(
        "28.20",
        "Petição de trâmite prioritário não conhecida",
        "O INPI não aceitou analisar o pedido de trâmite prioritário; os motivos estão no despacho.",
    ),
    # Prazo de 60 dias sem início definido; afeta só a prioridade, não o pedido.
    _patente(
        "28.21",
        "Exigência formal de trâmite prioritário",
        "O pedido de trâmite prioritário tem problemas formais, que podem ser corrigidos em 60 dias (GRU 206). "
        "Isso afeta só a prioridade, não o pedido de patente.",
    ),
    _patente(
        "28.22",
        "Requerimento de trâmite prioritário encaminhado para confirmação tecnológica.",
        "As condições formais do trâmite prioritário foram atendidas; falta confirmar a tecnologia.",
    ),
    _patente(
        "28.23",
        "Requerimento de trâmite prioritário encaminhado para avaliação do dirigente máximo da unidade",
        "O pedido de trâmite prioritário foi enviado para avaliação da direção, por ser um caso não previsto.",
    ),
    _patente(
        "28.30",
        "Trâmite prioritário admitido",
        "Boa notícia: o pedido terá trâmite prioritário (análise mais rápida) em todo o INPI.",
    ),
    _patente(
        "28.31",
        "Trâmite prioritário por emergência nacional ou interesse público",
        "O pedido terá trâmite prioritário porque o assunto está coberto por ato do Governo Federal (emergência "
        "nacional ou interesse público).",
    ),
    _patente(
        "28.32",
        "Trâmite prioritário por solicitação do Ministério da Saúde admitido",
        "O pedido terá trâmite prioritário a pedido do Ministério da Saúde, por ser estratégico para o SUS.",
    ),
    _patente(
        "28.40",
        "Trâmite prioritário não admitido",
        "O pedido de trâmite prioritário não foi aceito; os motivos estão no despacho.",
    ),
    _patente(
        "28.42",
        "Trâmite prioritário por solicitação do Ministério da Saúde não admitido",
        "O pedido de trâmite prioritário feito pelo Ministério da Saúde não foi aceito; os motivos estão no "
        "despacho.",
    ),
    _patente(
        "28.90",
        "Retificação de despacho de trâmite prioritário",
        "O INPI corrigiu um erro num despacho de trâmite prioritário. A data de publicação e os prazos não "
        "mudam.",
    ),
    _patente(
        "28.91",
        "Republicação de despacho de trâmite prioritário",
        "O INPI publicou de novo um despacho de trâmite prioritário que tinha saído com erro. A data de "
        "publicação e os prazos passam a contar desta publicação.",
    ),
    _patente(
        "28.92",
        "Publicação de despacho de trâmite prioritário anulada",
        "O INPI cancelou a publicação de um despacho de trâmite prioritário porque ela foi indevida.",
    ),
    _patente(
        "28.93",
        "Trâmite prioritário cassado",
        "O trâmite prioritário do pedido foi cancelado; os motivos estão no despacho.",
    ),
    # Sobrestamento (p. 41)
    _patente(
        "29.1",
        "Exame técnico sobrestado por matéria não publicada",
        "O exame técnico está parado porque existe um documento ainda não publicado que influencia a decisão.",
    ),
    _patente(
        "29.2",
        "Pedido de patente sobrestado por determinação judicial",
        "Todos os atos do pedido estão parados por ordem da Justiça.",
    ),
    _patente(
        "29.3",
        "Patente sobrestada por determinação judicial",
        "Todos os atos da patente estão parados por ordem da Justiça.",
    ),
    _patente(
        "29.10",
        "Dessobrestamento",
        "O pedido, o exame técnico ou a patente voltou a andar.",
    ),
    _patente("29.11", "Retificação", _RETIFICACAO_SEM_MUDAR_PRAZO),
    _patente("29.12", "Publicação Anulada", _PUBLICACAO_ANULADA),
    # Presidência - Recurso (pp. 42-43)
    _patente(
        "100",
        "Recurso conhecido e provido. Reformada a decisão recorrida e deferido o pedido.",
        "Boa notícia: o recurso foi aceito, a decisão foi mudada e o pedido foi aprovado. A carta-patente será "
        "expedida sem custo.",
    ),
    _patente(
        "100.1",
        "Recurso conhecido e provido. Reformada a decisão recorrida e deferido o pedido.",
        "Boa notícia: o recurso foi aceito, a decisão foi mudada e o pedido foi aprovado. A carta-patente será "
        "expedida sem custo.",
    ),
    _patente(
        "100.2",
        "Recurso conhecido e provido. Anulado o indeferimento e retorno dos autos à primeira instância para "
        "continuação do exame.",
        "Boa notícia: o recurso foi aceito e a negativa do pedido foi anulada. O pedido volta para o exame.",
    ),
    _patente(
        "102",
        "Recurso conhecido e provido. Desarquivado o processo para prosseguir o exame",
        "Boa notícia: o recurso foi aceito e o pedido foi desarquivado para continuar o exame.",
    ),
    _patente(
        "103",
        "Recurso conhecido e provido. Desarquivada a petição",
        "Boa notícia: o recurso foi aceito e a petição foi desarquivada.",
    ),
    _patente(
        "104",
        "Recurso conhecido e provido. Reformada a Decisão recorrida.",
        "Boa notícia: o recurso foi aceito e a decisão foi mudada. Confira o complemento.",
    ),
    _patente(
        "106",
        "Decisão de Recurso: Mantida a Prioridade Unionista",
        "O recurso decidiu manter a prioridade reivindicada pelo pedido (prioridade unionista).",
    ),
    _patente(
        "111",
        "Recurso conhecido e negado provimento. Mantido o indeferimento do pedido",
        "O recurso foi analisado e negado: o pedido continua negado.",
    ),
    _patente(
        "112",
        "Recurso conhecido e negado provimento. Mantido o arquivamento do pedido",
        "O recurso foi analisado e negado: o pedido continua arquivado.",
    ),
    _patente(
        "113",
        "Recurso conhecido e negado provimento. Mantido o arquivamento da petição",
        "O recurso foi analisado e negado: a petição continua arquivada.",
    ),
    _patente(
        "115",
        "Recurso conhecido e negado provimento. Mantida a Decisão recorrida.",
        "O recurso foi analisado e negado: a decisão foi mantida.",
    ),
    _patente(
        "116",
        "Decisão de Recurso: perda da Prioridade",
        "O recurso decidiu que o pedido perde a prioridade reivindicada.",
    ),
    _patente(
        "120",
        "Tome Conhecimento do Parecer Técnico",
        "Há um parecer técnico da fase de recurso para ser lido. Confira o parecer na Busca de Processos do "
        "INPI.",
    ),
    _patente(
        "121",
        "Exigência",
        "Na fase de recurso, o INPI fez uma exigência. Veja o parecer na Busca de Processos. " + _PRAZO_SEM_INICIO,
        requires_action=True,
    ),
    _patente(
        "130",
        "Recurso Prejudicado",
        "O recurso não será julgado porque ficou prejudicado (perdeu o sentido). Confira o motivo no "
        "complemento.",
    ),
    _patente(
        "131",
        "Recurso Não Conhecido",
        "O INPI não aceitou analisar o recurso. Confira o motivo no complemento.",
    ),
    _patente("132", "Anulada a Decisão", _DECISAO_ANULADA),
    _patente("133", "Retificação", _RETIFICACAO),
    _patente("134", "Desistência do Recurso", "Houve desistência do recurso."),
    _patente("135", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _patente("136", "Petição não Conhecida", _PETICAO_NAO_CONHECIDA),
    _patente(
        "137",
        "Petição Prejudicada",
        "Uma petição deste processo não será analisada porque ficou prejudicada. Confira o complemento.",
    ),
    _patente("138", "Petição Arquivada", _PETICAO_ARQUIVADA),
    _patente("139", "Republicação", _REPUBLICACAO),
    _patente("140", "Devolução de Prazo", _DEVOLUCAO_DE_PRAZO_SEM_TEXTO, requires_action=True),
    # Prazo contraditório na própria tabela: "60 (noventa) dias".
    _patente(
        "141",
        "Notificações Diversas",
        "O INPI parou o andamento do pedido e pede manifestação. Veja o parecer na Busca de Processos. A tabela "
        "informa o prazo de forma contraditória (\"60 (noventa) dias\"), por isso o sistema não calcula a data. "
        "Sem manifestação, a petição relacionada não é analisada.",
        requires_action=True,
    ),
    # Presidência - Nulidade (pp. 44-45)
    _patente(
        "200",
        "Processo administrativo de Nulidade conhecido e provido. Declarada a Nulidade da Patente.",
        "O processo de nulidade foi decidido contra a patente: ela foi declarada nula.",
    ),
    _patente(
        "201",
        "Processo administrativo de Nulidade conhecido, negado provimento. Mantida a concessão da Patente.",
        "Boa notícia: o pedido de nulidade foi negado e a patente continua valendo.",
    ),
    _patente(
        "204",
        "Processo administrativo de Nulidade conhecido, provido parcialmente. Mantida a concessão da Patente.",
        "O pedido de nulidade foi aceito só em parte e a patente continua concedida. Confira o complemento para "
        "ver o que mudou.",
    ),
    _patente(
        "205",
        "Intimação para manifestação por parte do titular e do requerente",
        "O INPI pede que o titular e quem pediu a nulidade se manifestem. Veja o parecer na Busca de Processos. "
        + _PRAZO_SEM_INICIO,
        requires_action=True,
    ),
    _patente("206", "Petição não Conhecida", _PETICAO_NAO_CONHECIDA),
    _patente("210", "Nulidade não conhecida", "O INPI não aceitou analisar o pedido de nulidade."),
    _patente("211", "Sobrestado o Processo Administrativo", "O processo de nulidade está parado."),
    _patente(
        "212",
        "Nulidade prejudicada",
        "O processo de nulidade não será julgado porque ficou prejudicado.",
    ),
    _patente("213", "Decisão Anulada", _DECISAO_ANULADA),
    _patente("214", "Notificações Diversas", "Aviso sobre o processo de nulidade. Confira o complemento."),
    _patente("215", "Retificações Diversas", _RETIFICACAO),
    _patente("216", "Petição não Conhecida", _PETICAO_NAO_CONHECIDA),
    _patente("217", "Petição Arquivada", _PETICAO_ARQUIVADA),
    _patente("218", "Devolução de Prazo", _DEVOLUCAO_DE_PRAZO_SEM_TEXTO, requires_action=True),
    _patente("219", "Republicação", _REPUBLICACAO),
    _patente("220", "Publicação Anulada", _PUBLICACAO_ANULADA),
)


# --- Programas de computador (PDF "Tabela de Códigos de Despachos - Programas de Computador", 5 páginas) ----------
# Códigos guardados como na tabela, com o zero à esquerda ("080").

_PROGRAMAS: tuple[DispatchCodeEntry, ...] = (
    # O texto da tabela para este código está truncado ("Formulada exigência ... formulada.").
    _programa(
        "080",
        "Publicação de pedido de Registro de Programa de Computador",
        "O pedido de registro do programa foi publicado. O texto da tabela oficial para este código está "
        "confuso; confira o complemento do despacho.",
    ),
    # A tabela conta o prazo "da data da notificação"; confirmado em 28/11/2026 que a notificação é a própria
    # publicação na RPI.
    _programa(
        "082",
        "Pedido em exigência devido a irregularidades",
        "O INPI encontrou irregularidades e parou o pedido de registro até que as exigências sejam atendidas ou "
        "contestadas. É preciso responder em até 60 dias da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "090",
        "Deferimento de pedido de registro de programa de computador",
        "Boa notícia: o INPI aprovou o registro do programa. Outras pessoas podem recorrer em até 60 dias.",
    ),
    _programa(
        "091",
        "Alteração de Nome Deferida",
        "O INPI aceitou a alteração de nome. Interessados podem recorrer em até 60 dias.",
    ),
    _programa(
        "092",
        "Alteração de Nome em Exigência",
        "O INPI pediu ajustes no pedido de alteração de nome. Cumpra a exigência em até 60 dias da publicação, "
        "senão a alteração é negada.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "093",
        "Alteração de Nome Indeferida",
        "O INPI negou a alteração de nome pedida. Se discordar, é possível recorrer em até 60 dias da "
        "publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "094",
        "Alteração de Razão Social Deferida",
        "O INPI aceitou a alteração de razão social. Interessados podem recorrer em até 60 dias.",
    ),
    _programa(
        "095",
        "Alteração de Razão Social em Exigência",
        "O INPI pediu ajustes no pedido de alteração de razão social. Cumpra a exigência em até 60 dias da "
        "publicação, senão a alteração é negada.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "096",
        "Alteração de Razão Social Indeferida",
        "O INPI negou a alteração de razão social pedida. Se discordar, é possível recorrer em até 60 dias da "
        "publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "097",
        "Alteração de Endereço Deferida",
        "O INPI aceitou a alteração de endereço. Interessados podem recorrer em até 60 dias.",
    ),
    _programa(
        "098",
        "Alteração de Endereço em Exigência",
        "O INPI pediu ajustes no pedido de alteração de endereço. Cumpra a exigência em até 60 dias da "
        "publicação, senão a alteração é negada.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "099",
        "Alteração de Endereço Indeferida",
        "O INPI negou a alteração de endereço pedida. Se discordar, é possível recorrer em até 60 dias da "
        "publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "100",
        "Transferência de Titularidade Deferida",
        "O INPI aceitou a transferência de titularidade. Interessados podem recorrer em até 60 dias.",
    ),
    _programa(
        "101",
        "Transferência de Titularidade em Exigência",
        "O INPI pediu ajustes no pedido de transferência de titularidade. Cumpra a exigência em até 60 dias da "
        "publicação, senão a transferência é negada.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "102",
        "Transferência de Titularidade Indeferida",
        "O INPI negou a transferência de titularidade pedida. Se discordar, é possível recorrer em até 60 dias "
        "da publicação.",
        requires_action=True,
        deadline_days=60,
    ),
    _programa(
        "104",
        "Petição não conhecida",
        "O INPI não aceitou analisar uma petição, por falta de base legal ou de comprovante de pagamento. "
        "Confira o complemento.",
    ),
    _programa(
        "105",
        "Desistência de pedido de registro de programa de computador homologada",
        "O INPI aceitou a desistência do pedido de registro do programa.",
    ),
    _programa(
        "106",
        "Renúncia ao registro de programa de computador homologada",
        "O INPI aceitou a renúncia ao registro do programa.",
    ),
    # Título truncado na própria tabela oficial ("homologad"): mantido como está.
    _programa(
        "107",
        "Renúncia ao sigilo da documentação técnica homologad",
        "O INPI registrou a renúncia ao sigilo da documentação técnica do programa.",
    ),
    _programa(
        "108",
        "Registro/pedido de registro subjudice",
        "Existe uma ação na Justiça sobre este registro ou pedido.",
    ),
    _programa(
        "109",
        "Anotação de limitação ou ônus",
        "O INPI registrou uma limitação ou ônus sobre o registro, conforme o complemento.",
    ),
    _programa("110", "Publicação Anulada", _PUBLICACAO_ANULADA),
    _programa("111", "Despacho Anulado", _DESPACHO_ANULADO),
    _programa("112", "Decisão Anulada", _DECISAO_ANULADA),
    _programa("113", "Retificação", _RETIFICACAO_SEM_MUDAR_PRAZO),
    _programa("114", "Republicação", _REPUBLICACAO),
    _programa(
        "115",
        "Recurso contra o deferimento",
        "Alguém apresentou recurso contra a aprovação do registro do programa. O titular pode responder "
        "(contrarrazões) em até 30 dias da publicação.",
        requires_action=True,
        deadline_days=30,
    ),
    _programa(
        "120",
        "Concessão do Registro",
        "Boa notícia: o certificado de registro do programa foi expedido e será enviado ao titular ou ao "
        "procurador.",
    ),
    _programa("704", "Transferência de Titularidade", _CERTIFICADO_ATUALIZADO),
    _programa(
        "709",
        "Renúncia do Registro",
        "O INPI aceitou a renúncia ao registro do programa e retirou o certificado do portal.",
    ),
    _programa(
        "730",
        "Expedição do Certificado de Registro",
        "Boa notícia: o certificado de registro do programa está disponível no portal do INPI.",
    ),
    _programa("731", "Alteração de Nome", _CERTIFICADO_ATUALIZADO),
    _programa("732", "Alteração de Razão Social", _CERTIFICADO_ATUALIZADO),
    _programa("733", "Alteração de endereço", _CERTIFICADO_ATUALIZADO),
    _programa("734", "Transferência de Titularidade", _CERTIFICADO_ATUALIZADO),
    _programa(
        "736",
        "Revogação ou renúncia da procuração",
        "A procuração apresentada antes foi revogada ou renunciada.",
    ),
    _programa("737", "Alteração de nome ou razão social judicial", _CERTIFICADO_ATUALIZADO),
    _programa("738", "Alteração de sede judicial", _CERTIFICADO_ATUALIZADO),
    _programa("739", "Alteração de endereço judicial", _CERTIFICADO_ATUALIZADO),
    _programa("740", "Alteração de titularidade judicial", _CERTIFICADO_ATUALIZADO),
    _programa(
        "741",
        "Notificação de encerramento de pedido sub judice",
        "Uma decisão da Justiça encerrou a suspensão do andamento do registro.",
    ),
    _programa(
        "742",
        "Petição não conhecida",
        "Uma irregularidade impediu o INPI de executar o serviço pedido. O motivo está no complemento.",
    ),
    _programa(
        "743",
        "Nulidade Administrativa",
        "O registro do programa foi anulado pelo INPI e o certificado foi retirado do portal.",
    ),
    _programa(
        "744",
        "Nulidade judicial",
        "O registro do programa foi anulado pela Justiça e o certificado foi retirado do portal.",
    ),
    _programa(
        "745",
        "Restauração judicial",
        "A Justiça restaurou o registro do programa; o certificado atualizado está no portal do INPI.",
    ),
    _programa("746", "Publicação anulada", _PUBLICACAO_ANULADA),
    _programa(
        "747",
        "Correção de dados no Certificado de Registro devido à falha do interessado",
        _CERTIFICADO_ATUALIZADO,
    ),
)

DISPATCH_CODES: tuple[DispatchCodeEntry, ...] = _PATENTES + _PROGRAMAS
