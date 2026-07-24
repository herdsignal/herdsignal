import { useCallback, useEffect, useRef, useState } from 'react'
import { getPortfolioHistory, getPortfolioSummary } from '../../api/herdApi'

export function usePortfolioHistory(period) {
  const [points, setPoints] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const requestId = useRef(0)

  const fetchData = useCallback(async () => {
    const currentRequest = ++requestId.current
    setLoading(true)
    setError(null)
    const [historyResult, summaryResult] = await Promise.allSettled([
      getPortfolioHistory(period),
      getPortfolioSummary(),
    ])
    if (currentRequest !== requestId.current) return

    if (historyResult.status === 'fulfilled') {
      setPoints(historyResult.value.data?.data?.points ?? [])
    } else {
      setPoints([])
      setError('히스토리 데이터를 불러올 수 없습니다.')
    }
    if (summaryResult.status === 'fulfilled') {
      setSummary(summaryResult.value.data?.data ?? null)
    }
    setLoading(false)
  }, [period])

  useEffect(() => { fetchData() }, [fetchData])
  useEffect(() => () => { requestId.current += 1 }, [])

  return { points, summary, loading, error, fetchData }
}
