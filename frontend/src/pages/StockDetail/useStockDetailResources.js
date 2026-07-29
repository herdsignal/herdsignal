import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getDailyHerdObservation,
  getHerdObservation,
  getHerdEpisodeStudy,
  getHistoricalS1Context,
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
  const [dailyObservation, setDailyObservation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [herdTimeline, setHerdTimeline] = useState([])
  const [timelineMeta, setTimelineMeta] = useState(null)
  const [historyPeriod, setHistoryPeriod] = useState('1y')
  const [historyLoading, setHistoryLoading] = useState(false)
  const [financials, setFinancials] = useState(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)
  const [episodeStudy, setEpisodeStudy] = useState(null)
  const [episodeLoading, setEpisodeLoading] = useState(false)
  const [historicalContext, setHistoricalContext] = useState(null)
  const [historicalContextLoading, setHistoricalContextLoading] = useState(false)
  const herdRequest = useRef(0)

  useEffect(() => {
    setObservation(null)
    setDailyObservation(null)
    setError(null)
  }, [normalizedTicker])

  useEffect(() => {
    let active = true
    setHistoricalContextLoading(true)
    setHistoricalContext(null)
    getHistoricalS1Context(normalizedTicker)
      .then((response) => {
        if (active) setHistoricalContext(response.data?.data ?? null)
      })
      .catch(() => {
        if (active) setHistoricalContext(null)
      })
      .finally(() => {
        if (active) setHistoricalContextLoading(false)
      })
    return () => {
      active = false
    }
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
      const [observationResult, dailyResult] = await Promise.allSettled([
        getHerdObservation(normalizedTicker),
        getDailyHerdObservation(normalizedTicker),
      ])
      if (requestId !== herdRequest.current) return
      if (observationResult.status === 'rejected') {
        throw observationResult.reason
      }
      const observationData = observationResult.value.data?.data ?? null
      setObservation(observationData)
      setDailyObservation(
        dailyResult.status === 'fulfilled'
          ? dailyResult.value.data?.data ?? null
          : null,
      )
    } catch (requestError) {
      if (requestId === herdRequest.current) {
        const unavailable = requestError.response?.status
          ? `${displayTicker} 종목의 HERD 관찰 API를 확인할 수 없습니다.\n이전 모델 점수로 대체 표시하지 않습니다.`
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
    setTimelineMeta(null)
    getHerdPriceTimeline(
      normalizedTicker,
      OBSERVATION_TIMELINE_LIMIT,
    )
      .then((response) => {
        if (active) {
          const timeline = response.data?.data ?? null
          setHerdTimeline(normalizeHerdPriceTimeline(timeline?.points))
          setTimelineMeta(timeline)
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
    dailyObservation,
    loading,
    error,
    herdHistory,
    herdTimeline,
    timelineMeta,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    financials,
    financialsLoading,
    episodeStudy,
    episodeLoading,
    historicalContext,
    historicalContextLoading,
    fetchData,
  }
}
