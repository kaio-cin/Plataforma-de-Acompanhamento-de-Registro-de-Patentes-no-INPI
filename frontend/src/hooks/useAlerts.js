import { useCallback, useEffect, useState } from 'react'

import { listAlerts, markAlertAsRead, notifyAlertsChanged } from '../api/alerts'
import { replaceAlert } from '../utils/alerts'

/** Carrega os alertas do usuário logado e permite marcá-los como lidos (US12). */
export function useAlerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    listAlerts()
      .then((data) => {
        if (!cancelled) setAlerts(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    setReloadKey((key) => key + 1)
  }, [])

  /** Marca como lido, troca o item na lista e avisa o sininho. Em erro, a exceção chega a quem chamou. */
  const markAsRead = useCallback(async (id) => {
    const updated = await markAlertAsRead(id)
    setAlerts((current) => replaceAlert(current, updated))
    notifyAlertsChanged()
    return updated
  }, [])

  return { alerts, loading, error, reload, markAsRead }
}
