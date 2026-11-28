/** Regras de apresentação dos alertas (US12): prazo, filtros das abas, contador e atualização periódica. */

import { formatDate, todayIso } from './format'

/** Prazo a até este número de dias aparece em amarelo ("vence em breve"). */
export const DEADLINE_WARNING_DAYS = 15

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * Dias de `fromIso` até `toIso` (datas "AAAA-MM-DD"); negativo quando `toIso` já passou.
 * Usa Date.UTC com as partes da data, sem `new Date(string)`, para o fuso não trocar o dia.
 */
export function daysBetween(fromIso, toIso) {
  const toUtc = (iso) => {
    const [year, month, day] = iso.split('-').map(Number)
    return Date.UTC(year, month - 1, day)
  }
  return Math.round((toUtc(toIso) - toUtc(fromIso)) / DAY_MS)
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`

/**
 * Selo de prazo de um alerta: { tone, label } para o Badge.
 * critical = vencido ou vence hoje · warning = vence em até 15 dias ou exige ação sem data ·
 * info = prazo distante · neutral = informativo.
 */
export function deadlineInfo(alert, today = todayIso()) {
  if (!alert.requires_action) return { tone: 'neutral', label: 'Informativo' }
  if (!alert.deadline) return { tone: 'warning', label: 'Exige ação · prazo no despacho' }

  const days = daysBetween(today, alert.deadline)
  const date = formatDate(alert.deadline)
  if (days < 0) return { tone: 'critical', label: `Prazo vencido há ${plural(-days, 'dia', 'dias')}` }
  if (days === 0) return { tone: 'critical', label: 'Vence hoje' }
  if (days === 1) return { tone: 'warning', label: `Vence amanhã · ${date}` }
  if (days <= DEADLINE_WARNING_DAYS) return { tone: 'warning', label: `Vence em ${days} dias · ${date}` }
  return { tone: 'info', label: `Prazo: ${date}` }
}

/** Abas da tela de alertas. */
export const ALERT_TABS = [
  { id: 'todos', label: 'Todos' },
  { id: 'nao-lidos', label: 'Não lidos' },
  { id: 'acao', label: 'Exigem ação' },
]

const TAB_FILTERS = {
  todos: () => true,
  'nao-lidos': (alert) => !alert.is_read,
  acao: (alert) => alert.requires_action,
}

/** Alertas da aba escolhida, mantendo a ordem da API (mais novo primeiro). */
export function filterAlerts(alerts, tab) {
  return alerts.filter(TAB_FILTERS[tab] ?? TAB_FILTERS.todos)
}

/** Quantidade de alertas em cada aba: { todos, 'nao-lidos', acao }. */
export function countAlertsByTab(alerts) {
  return Object.fromEntries(ALERT_TABS.map(({ id }) => [id, filterAlerts(alerts, id).length]))
}

/** Troca na lista o alerta devolvido pela API (ex.: depois de marcar como lido). */
export function replaceAlert(alerts, updated) {
  return alerts.map((alert) => (alert.id === updated.id ? updated : alert))
}

/** Texto da bolinha do sininho: "9+" acima de 9; vazio quando não há não lidos. */
export function unreadBadgeText(count) {
  if (!count || count < 1) return ''
  return count > 9 ? '9+' : String(count)
}

/** Rótulo acessível do sininho. */
export function unreadLabel(count) {
  if (!count) return 'Alertas: nenhum não lido'
  return `Alertas: ${count} não ${count === 1 ? 'lido' : 'lidos'}`
}

/**
 * Caminho da tela de detalhe do ativo. A rota /ativos/:id ainda não existe (frente do Guilherme):
 * quando existir, a tela de alertas passa a usar este caminho no título do ativo.
 */
export function assetPath(assetId) {
  return `/ativos/${assetId}`
}

/**
 * Chama `refresh` agora e a cada `intervalMs`, só enquanto a aba estiver visível.
 * Ao esconder a aba, pausa; ao voltar, atualiza na hora e retoma. Retorna a função que encerra tudo.
 */
export function startVisiblePolling(refresh, intervalMs, doc = globalThis.document) {
  let timer = null

  const resume = () => {
    if (timer === null) timer = setInterval(refresh, intervalMs)
  }
  const pause = () => {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }
  function handleVisibility() {
    if (doc.hidden) {
      pause()
    } else {
      refresh()
      resume()
    }
  }

  if (!doc.hidden) {
    refresh()
    resume()
  }
  doc.addEventListener('visibilitychange', handleVisibility)

  return () => {
    pause()
    doc.removeEventListener('visibilitychange', handleVisibility)
  }
}
