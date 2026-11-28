import { useCallback, useEffect, useState } from 'react'

import { listDispatchCodes } from '../api/dispatchCodes'

/** Carrega o glossário de códigos de despacho. */
export function useDispatchCodes() {
  const [codes, setCodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    listDispatchCodes()
      .then((data) => {
        if (!cancelled) setCodes(data)
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

  return { codes, loading, error, reload }
}
