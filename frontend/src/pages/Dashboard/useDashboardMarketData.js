import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getSpyHerdHistory, getStockHerd } from '../../api/herdApi'
import { fetchExchangeRate } from '../../utils/currency'
import { getHerdMomentum } from '../../utils/herdMomentum'
import {
  CACHE_KEY_SPY,
  averageScoreForLastDays,
  isUsableSpyHistoryCache,
  readCache,
  spyHistoryCacheKey,
  writeCache,
} from './dashboardModel'

/** SPY 배너, 히스토리, 환율처럼 포트폴리오와 독립적인 시장 상태를 관리한다. */
export function useDashboardMarketData() {
  const [spyData, setSpyData] = useState(null)
  const [spyHistory, setSpyHistory] = useState([])
  const [spyStatsHistory, setSpyStatsHistory] = useState([])
  const [spyHistoryPeriod, setSpyHistoryPeriod] = useState('3y')
  const [spyHistoryLoading, setSpyHistoryLoading] = useState(false)
  const [spyTab, setSpyTab] = useState('overview')
  const [exchangeRate, setExchangeRate] = useState(null)
  const spyDataCache = useRef(null)
  const spyHistoryCache = useRef({})
  const requestSequence = useRef(0)

  useEffect(() => {
    const requestId = ++requestSequence.current
    const historyKey = spyHistoryCacheKey(spyHistoryPeriod)
    const herdCached = spyDataCache.current ?? readCache(CACHE_KEY_SPY)
    const rawHistoryCached = spyHistoryCache.current[spyHistoryPeriod] ?? readCache(historyKey)
    const historyCached = isUsableSpyHistoryCache(spyHistoryPeriod, rawHistoryCached)
      ? rawHistoryCached
      : null

    if (herdCached) {
      spyDataCache.current = herdCached
      setSpyData(herdCached)
    }
    if (historyCached) {
      spyHistoryCache.current[spyHistoryPeriod] = historyCached
      setSpyHistory(historyCached)
      setSpyHistoryLoading(false)
      if (spyHistoryPeriod === '3y') setSpyStatsHistory(historyCached)
    }
    if (herdCached && historyCached) return

    if (!herdCached) {
      getStockHerd('SPY')
        .then((res) => {
          if (requestId !== requestSequence.current) return
          const data = res.data?.data ?? null
          spyDataCache.current = data
          setSpyData(data)
          writeCache(CACHE_KEY_SPY, data)
        })
        .catch(() => {})
    }

    if (!historyCached) {
      setSpyHistoryLoading(true)
      setSpyHistory([])
      getSpyHerdHistory(spyHistoryPeriod)
        .then((res) => {
          if (requestId !== requestSequence.current) return
          const points = res.data?.data?.points ?? []
          spyHistoryCache.current[spyHistoryPeriod] = points
          setSpyHistory(points)
          writeCache(historyKey, points)
          if (spyHistoryPeriod === '3y') setSpyStatsHistory(points)
        })
        .catch(() => {})
        .finally(() => {
          if (requestId === requestSequence.current) setSpyHistoryLoading(false)
        })
    }
  }, [spyHistoryPeriod])

  useEffect(() => {
    fetchExchangeRate().then(setExchangeRate)
  }, [])

  const updateSpyData = useCallback((data) => {
    spyDataCache.current = data
    setSpyData(data)
    writeCache(CACHE_KEY_SPY, data)
  }, [])

  const spyScore = spyData?.herdV4 ?? spyData?.herdScore ?? 50
  const spyStage = spyData?.herdStage ?? 'Calm'
  const d1AvgPoint = useMemo(
    () => averageScoreForLastDays(spyStatsHistory, 1, spyScore),
    [spyStatsHistory, spyScore],
  )
  const m1AvgPoint = useMemo(
    () => averageScoreForLastDays(spyStatsHistory, 30, spyScore),
    [spyStatsHistory, spyScore],
  )
  const y1AvgPoint = useMemo(
    () => averageScoreForLastDays(spyStatsHistory, 365, spyScore),
    [spyStatsHistory, spyScore],
  )
  const spyMomentum = useMemo(
    () => getHerdMomentum(spyStatsHistory, spyScore, spyStage),
    [spyStatsHistory, spyScore, spyStage],
  )

  return {
    spyData,
    spyHistory,
    spyHistoryPeriod,
    setSpyHistoryPeriod,
    spyHistoryLoading,
    spyTab,
    setSpyTab,
    exchangeRate,
    updateSpyData,
    spyScore,
    spyStage,
    d1AvgPoint,
    m1AvgPoint,
    y1AvgPoint,
    spyMomentum,
  }
}
