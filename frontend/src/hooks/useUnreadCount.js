import { useEffect, useState } from 'react'

import { getUnreadCount, onAlertsChanged } from '../api/alerts'
import { startVisiblePolling } from '../utils/alerts'

/** Intervalo da atualização do sininho. Alertas novos só surgem quando a RPI é processada. */
export const UNREAD_POLL_MS = 2 * 60 * 1000

/**
 * Quantidade de alertas não lidos do usuário logado, para o sininho.
 * Atualiza ao abrir, a cada 2 minutos com a aba visível, ao voltar para a aba e quando um alerta muda.
 * Uma falha não mostra erro: o sininho só fica sem número.
 */
export function useUnreadCount() {
  const [count, setCount] = useState(0)

  useEffect(() => {
    let cancelled = false

    function refresh() {
      getUnreadCount()
        .then((value) => {
          if (!cancelled) setCount(value)
        })
        .catch(() => {
          if (!cancelled) setCount(0)
        })
    }

    const stopPolling = startVisiblePolling(refresh, UNREAD_POLL_MS)
    const unsubscribe = onAlertsChanged(refresh)
    return () => {
      cancelled = true
      stopPolling()
      unsubscribe()
    }
  }, [])

  return count
}
