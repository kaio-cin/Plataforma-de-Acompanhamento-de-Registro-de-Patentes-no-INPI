import { request } from './client'

/** GET /alerts/ — alertas do usuário logado, do mais novo para o mais antigo (US12) */
export function listAlerts() {
  return request('/alerts/')
}

/** GET /alerts/unread-count — quantidade de alertas não lidos, para o sininho */
export async function getUnreadCount() {
  const data = await request('/alerts/unread-count')
  return data.count
}

/** PATCH /alerts/{id}/read — marca um alerta como lido e devolve o alerta atualizado */
export function markAlertAsRead(id) {
  return request(`/alerts/${id}/read`, { method: 'PATCH' })
}

// Ouvintes avisados quando algum alerta muda (ex.: marcado como lido), para o sininho atualizar.
const changeListeners = new Set()

export function onAlertsChanged(listener) {
  changeListeners.add(listener)
  return () => changeListeners.delete(listener)
}

export function notifyAlertsChanged() {
  changeListeners.forEach((listener) => listener())
}
