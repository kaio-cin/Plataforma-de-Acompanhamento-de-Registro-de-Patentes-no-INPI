import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  assetPath,
  countAlertsByTab,
  daysBetween,
  deadlineInfo,
  filterAlerts,
  replaceAlert,
  startVisiblePolling,
  unreadBadgeText,
  unreadLabel,
} from './alerts'

const TODAY = '2026-11-28'

const alert = (overrides = {}) => ({
  id: 1,
  asset_id: 10,
  asset_title: 'Patente da autora',
  process_number: 'BR 10 2023 000001-1',
  dispatch_code: '6.1',
  dispatch_description: 'Exigência técnica',
  dispatch_plain_description: 'O INPI pediu ajustes no pedido.',
  publication_date: '2026-11-24',
  requires_action: true,
  deadline: '2027-02-22',
  is_read: false,
  created_at: '2026-11-25T10:00:00',
  ...overrides,
})

describe('daysBetween', () => {
  it('conta dias corridos, inclusive atravessando mês e ano', () => {
    expect(daysBetween('2026-11-28', '2026-11-28')).toBe(0)
    expect(daysBetween('2026-11-28', '2026-12-01')).toBe(3)
    expect(daysBetween('2026-12-30', '2027-01-02')).toBe(3)
    expect(daysBetween('2028-02-28', '2028-03-01')).toBe(2) // ano bissexto
  })

  it('fica negativo quando a data já passou', () => {
    expect(daysBetween('2026-11-28', '2026-11-25')).toBe(-3)
  })
})

describe('deadlineInfo', () => {
  it('prazo vencido é crítico e diz há quantos dias', () => {
    expect(deadlineInfo(alert({ deadline: '2026-11-25' }), TODAY)).toEqual({
      tone: 'critical',
      label: 'Prazo vencido há 3 dias',
    })
    expect(deadlineInfo(alert({ deadline: '2026-11-27' }), TODAY).label).toBe('Prazo vencido há 1 dia')
  })

  it('vence hoje é crítico', () => {
    expect(deadlineInfo(alert({ deadline: TODAY }), TODAY)).toEqual({ tone: 'critical', label: 'Vence hoje' })
  })

  it('vence amanhã e até 15 dias ficam em alerta, com a data', () => {
    expect(deadlineInfo(alert({ deadline: '2026-11-29' }), TODAY)).toEqual({
      tone: 'warning',
      label: 'Vence amanhã · 29 nov 2026',
    })
    expect(deadlineInfo(alert({ deadline: '2026-12-06' }), TODAY)).toEqual({
      tone: 'warning',
      label: 'Vence em 8 dias · 06 dez 2026',
    })
  })

  it('o limite da faixa de alerta é de 15 dias', () => {
    expect(deadlineInfo(alert({ deadline: '2026-12-13' }), TODAY).tone).toBe('warning') // 15 dias
    expect(deadlineInfo(alert({ deadline: '2026-12-14' }), TODAY)).toEqual({ tone: 'info', label: 'Prazo: 14 dez 2026' }) // 16
  })

  it('exige ação sem data usa o mesmo texto do glossário', () => {
    expect(deadlineInfo(alert({ deadline: null }), TODAY)).toEqual({
      tone: 'warning',
      label: 'Exige ação · prazo no despacho',
    })
  })

  it('despacho informativo não tem prazo', () => {
    expect(deadlineInfo(alert({ requires_action: false, deadline: null }), TODAY)).toEqual({
      tone: 'neutral',
      label: 'Informativo',
    })
  })

  it('usa a data local de hoje quando nenhuma é informada', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 10, 28, 23, 30)) // 28 nov 2026, 23h30 local
    expect(deadlineInfo(alert({ deadline: '2026-11-28' })).label).toBe('Vence hoje')
    vi.useRealTimers()
  })
})

describe('filtros e contagens das abas', () => {
  const alerts = [
    alert({ id: 1, requires_action: true, is_read: false }),
    alert({ id: 2, requires_action: false, deadline: null, is_read: true }),
    alert({ id: 3, requires_action: false, deadline: null, is_read: false }),
    alert({ id: 4, requires_action: true, is_read: true }),
  ]

  it('filtra por aba mantendo a ordem', () => {
    expect(filterAlerts(alerts, 'todos').map((a) => a.id)).toEqual([1, 2, 3, 4])
    expect(filterAlerts(alerts, 'nao-lidos').map((a) => a.id)).toEqual([1, 3])
    expect(filterAlerts(alerts, 'acao').map((a) => a.id)).toEqual([1, 4])
  })

  it('aba desconhecida mostra todos', () => {
    expect(filterAlerts(alerts, 'outra')).toHaveLength(4)
  })

  it('conta os alertas de cada aba', () => {
    expect(countAlertsByTab(alerts)).toEqual({ todos: 4, 'nao-lidos': 2, acao: 2 })
    expect(countAlertsByTab([])).toEqual({ todos: 0, 'nao-lidos': 0, acao: 0 })
  })

  it('troca só o alerta atualizado', () => {
    const updated = { ...alerts[0], is_read: true }
    const result = replaceAlert(alerts, updated)

    expect(result[0]).toBe(updated)
    expect(result.slice(1)).toEqual(alerts.slice(1))
    expect(alerts[0].is_read).toBe(false) // não altera a lista original
  })
})

describe('sininho', () => {
  it('mostra o número até 9 e "9+" acima disso', () => {
    expect(unreadBadgeText(0)).toBe('')
    expect(unreadBadgeText(1)).toBe('1')
    expect(unreadBadgeText(9)).toBe('9')
    expect(unreadBadgeText(10)).toBe('9+')
  })

  it('tem rótulo acessível no singular e no plural', () => {
    expect(unreadLabel(0)).toBe('Alertas: nenhum não lido')
    expect(unreadLabel(1)).toBe('Alertas: 1 não lido')
    expect(unreadLabel(3)).toBe('Alertas: 3 não lidos')
  })
})

describe('assetPath', () => {
  it('aponta para o detalhe do ativo', () => {
    expect(assetPath(7)).toBe('/ativos/7')
  })
})

describe('startVisiblePolling', () => {
  const INTERVAL = 120_000

  /** Documento falso: os testes rodam em Node, sem navegador. */
  function fakeDocument(hidden = false) {
    const doc = new EventTarget()
    doc.hidden = hidden
    doc.setHidden = (value) => {
      doc.hidden = value
      doc.dispatchEvent(new Event('visibilitychange'))
    }
    return doc
  }

  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('atualiza na hora e depois a cada intervalo', () => {
    const refresh = vi.fn()
    const stop = startVisiblePolling(refresh, INTERVAL, fakeDocument())

    expect(refresh).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(INTERVAL * 2)
    expect(refresh).toHaveBeenCalledTimes(3)
    stop()
  })

  it('pausa com a aba escondida e retoma com uma atualização imediata', () => {
    const refresh = vi.fn()
    const doc = fakeDocument()
    const stop = startVisiblePolling(refresh, INTERVAL, doc)

    doc.setHidden(true)
    vi.advanceTimersByTime(INTERVAL * 5)
    expect(refresh).toHaveBeenCalledTimes(1) // só a inicial

    doc.setHidden(false)
    expect(refresh).toHaveBeenCalledTimes(2) // imediata ao voltar
    vi.advanceTimersByTime(INTERVAL)
    expect(refresh).toHaveBeenCalledTimes(3) // retomou o intervalo
    stop()
  })

  it('começando com a aba escondida, só atualiza quando ela aparece', () => {
    const refresh = vi.fn()
    const doc = fakeDocument(true)
    const stop = startVisiblePolling(refresh, INTERVAL, doc)

    vi.advanceTimersByTime(INTERVAL * 3)
    expect(refresh).not.toHaveBeenCalled()

    doc.setHidden(false)
    expect(refresh).toHaveBeenCalledTimes(1)
    stop()
  })

  it('não acumula dois intervalos se a aba "aparecer" duas vezes seguidas', () => {
    const refresh = vi.fn()
    const doc = fakeDocument()
    const stop = startVisiblePolling(refresh, INTERVAL, doc)

    doc.setHidden(false)
    refresh.mockClear()
    vi.advanceTimersByTime(INTERVAL)
    expect(refresh).toHaveBeenCalledTimes(1)
    stop()
  })

  it('depois de encerrado, não atualiza mais nem escuta a aba', () => {
    const refresh = vi.fn()
    const doc = fakeDocument()
    const stop = startVisiblePolling(refresh, INTERVAL, doc)

    stop()
    vi.advanceTimersByTime(INTERVAL * 3)
    doc.setHidden(true)
    doc.setHidden(false)
    expect(refresh).toHaveBeenCalledTimes(1)
  })
})
