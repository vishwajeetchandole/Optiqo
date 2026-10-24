import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * Generic data-fetching hook that respects VITE_USE_MOCKS.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useApi(serviceFn, params)
 *
 * - serviceFn: an async function from src/services/ (or mock resolver)
 * - params: object passed as the first argument to serviceFn
 *   (changing params triggers a re-fetch)
 *
 * Returns:
 *   data        – resolved value (null while loading)
 *   loading     – boolean
 *   error       – Error | null
 *   isMock      – boolean (true when response carries source:"mock")
 *   refetch()   – manually re-trigger the fetch
 */
export function useApi(serviceFn, params) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [isMock, setIsMock]   = useState(false)
  const fetchCount = useRef(0)

  const fetch = useCallback(async () => {
    if (!serviceFn) return
    setLoading(true)
    setError(null)
    const id = ++fetchCount.current
    try {
      const result = await serviceFn(params)
      if (id !== fetchCount.current) return // stale response
      setData(result)
      setIsMock(result?.source === 'mock')
    } catch (err) {
      if (id !== fetchCount.current) return
      setError(err)
    } finally {
      if (id === fetchCount.current) setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceFn, JSON.stringify(params)])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, isMock, refetch: fetch }
}
