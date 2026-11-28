import { request } from './client'

/** GET /dispatch-codes/ — glossário de códigos de despacho do INPI (todos os perfis) */
export function listDispatchCodes() {
  return request('/dispatch-codes/')
}
