import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getUnreadCount, listAlerts, markAlertAsRead, notifyAlertsChanged, onAlertsChanged } from './alerts'
import { ApiError, tokenStorage } from './client'

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

let fetchMock

beforeEach(() => {
  // localStorage em memória (os testes rodam em Node, sem navegador).
  const store = new Map()
  vi.stubGlobal('localStorage', {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
  })
  tokenStorage.set('abc.def.ghi')
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api de alertas', () => {
  it('lista os alertas com GET /alerts/ e o token', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, [{ id: 1 }]))

    expect(await listAlerts()).toEqual([{ id: 1 }])
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/alerts\/$/)
    expect(options.method).toBe('GET')
    expect(options.headers.Authorization).toBe('Bearer abc.def.ghi')
  })

  it('devolve só o número do contador de não lidos', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { count: 3 }))

    expect(await getUnreadCount()).toBe(3)
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/alerts\/unread-count$/)
  })

  it('marca como lido com PATCH /alerts/{id}/read, sem corpo', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { id: 7, is_read: true }))

    expect(await markAlertAsRead(7)).toEqual({ id: 7, is_read: true })
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/alerts\/7\/read$/)
    expect(options.method).toBe('PATCH')
    expect(options.body).toBeUndefined()
  })

  it('repassa a mensagem do 404 de alerta de outro usuário', async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: 'Alerta não encontrado.' }))

    const error = await markAlertAsRead(99).catch((err) => err)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(404)
    expect(error.message).toBe('Alerta não encontrado.')
  })
})

describe('aviso de mudança nos alertas', () => {
  it('chama os ouvintes inscritos e para de chamar depois de cancelar', () => {
    const listener = vi.fn()
    const unsubscribe = onAlertsChanged(listener)

    notifyAlertsChanged()
    unsubscribe()
    notifyAlertsChanged()

    expect(listener).toHaveBeenCalledOnce()
  })
})
