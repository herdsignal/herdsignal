import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getHerdObservation,
  getHerdEpisodeStudy,
  getHerdPriceTimeline,
  getStockFinancials,
} from '../../api/herdApi'
import {
  normalizeHerdPriceTimeline,
  OBSERVATION_TIMELINE_LIMIT,
  selectObservationHistory,
} from '../../utils/herdObservation'
import { API_HOST } from './stockDetailModel'

export function useStockDetailResources(normalizedTicker, displayTicker) {
  const [observation, setObservation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [herdTimeline, setHerdTimeline] = useState([])
  const [historyPeriod, setHistoryPeriod] = useState('1y')
  const [historyLoading, setHistoryLoading] = useState(false)
  const [financials, setFinancials] = useState(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)
  const [episodeStudy, setEpisodeStudy] = useState(null)
  const [episodeLoading, setEpisodeLoading] = useState(false)
  const herdRequest = useRef(0)

  useEffect(() => {
    setObservation(null)
    setError(null)
  }, [normalizedTicker])

  useEffect(() => {
    let active = true
    setEpisodeLoading(true)
    setEpisodeStudy(null)
    getHerdEpisodeStudy(normalizedTicker)
      .then((response) => {
        if (active) setEpisodeStudy(response.data?.data ?? null)
      })
      .catch(() => {
        if (active) setEpisodeStudy(null)
      })
      .finally(() => {
        if (active) setEpisodeLoading(false)
      })
    return () => {
      active = false
    }
  }, [normalizedTicker])

  const fetchData = useCallback(async () => {
    const requestId = ++herdRequest.current
    setLoading(true)
    setError(null)
    try {
      const observationResult = await getHerdObservation(normalizedTicker)
      if (requestId !== herdRequest.current) return
      const observationData = observationResult.data?.data ?? null
      setObservation(observationData)
    } catch (requestError) {
      if (requestId === herdRequest.current) {
        const unavailable = requestError.response?.status
          ? `${displayTicker} 종목의 S1 관찰 API를 확인할 수 없습니다.\n기존 v4 점수로 대체하지 않습니다.`
          : `백엔드 서버에 연결할 수 없습니다.\n${API_HOST}이 실행 중인지 확인해주세요.`
        setError(unavailable)
      }
    } finally {
      if (requestId === herdRequest.current) setLoading(false)
    }
  }, [displayTicker, normalizedTicker])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    let active = true
    setHistoryLoading(true)
    setHerdTimeline([])
    getHerdPriceTimeline(
      normalizedTicker,
      OBSERVATION_TIMELINE_LIMIT,
    )
      .then((response) => {
        if (active) {
          setHerdTimeline(normalizeHerdPriceTimeline(
            response.data?.data?.points,
          ))
        }
      })
      .catch(() => {
        if (active) setHerdTimeline([])
      })
      .finally(() => {
        if (active) setHistoryLoading(false)
      })
    return () => {
      active = false
    }
  }, [normalizedTicker])

  const herdHistory = useMemo(
    () => selectObservationHistory(herdTimeline, historyPeriod),
    [herdTimeline, historyPeriod],
  )

  useEffect(() => {
    let active = true
    setFinancialsLoading(true)
    setFinancials(null)
    getStockFinancials(normalizedTicker)
      .then((response) => {
        if (active) setFinancials(response.data?.data ?? null)
      })
      .catch(() => {
        if (active) setFinancials(null)
      })
      .finally(() => {
        if (active) setFinancialsLoading(false)
      })
    return () => {
      active = false
    }
  }, [normalizedTicker])

  return {
    observation,
    loading,
    error,
    herdHistory,
    herdTimeline,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    financials,
    financialsLoading,
    episodeStudy,
    episodeLoading,
    fetchData,
  }
}
