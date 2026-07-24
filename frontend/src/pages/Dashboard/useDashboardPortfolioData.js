import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getCashBalance,
  getPortfolio,
  getHerdObservations,
  getPortfolioRealtime,
  getPortfolioSummary,
  getHerdObservation,
} from '../../api/herdApi'
import { targetWeightsFromPortfolio } from '../../utils/portfolioTools'
import {
  API_HOST,
  CACHE_KEY_HERD,
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_REALTIME,
  CACHE_KEY_TIME,
  ensureDashboardCacheVersion,
  isDashboardCacheFresh,
  normalizePortfolioSummary,
  readUserCache,
  refreshResultText,
  saveCacheTime,
  userCacheKey,
  writeUserCache,
} from './dashboardModel'
import { observationBatchToMap } from '../../utils/herdObservation'

function herdStocksToMap(stocks = []) {
  return Object.fromEntries(stocks.map((item) => [item.ticker, item]))
}

function observationResponseToCacheData(response) {
  const batch = response?.data?.data
  return {
    stocks: Object.values(observationBatchToMap(batch)),
    stateModelVersion: 'HERD_STATE_S1',
  }
}

function getPortfolioObservations(portfolio) {
  const tickers = (portfolio ?? []).map((item) => item.ticker).filter(Boolean)
  return tickers.length > 0
    ? getHerdObservations(tickers)
    : Promise.resolve({ data: { data: { observations: [] } } })
}

function withCash(summary, cashBalance) {
  if (!summary) return summary
  const investedValue = Number(summary.invested_value ?? summary.total_value ?? 0)
  const cash = Number(cashBalance ?? 0)
  return {
    ...summary,
    cash_balance: cash,
    total_value: investedValue + cash,
    total_asset_value: investedValue + cash,
  }
}

export function useDashboardPortfolioData({
  userId,
  setTargetWeights,
  updateSpyData,
  fetchDataStatus,
}) {
  const [portfolio, setPortfolio] = useState([])
  const [summary, setSummary] = useState(null)
  const [herdMap, setHerdMap] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshNotice, setRefreshNotice] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(() => {
    const time = localStorage.getItem(userCacheKey(CACHE_KEY_TIME, userId))
    return time ? new Date(time) : null
  })
  const [cashBalance, setCashBalance] = useState(0)
  const [cashDraft, setCashDraft] = useState('')
  const refreshNoticeTimer = useRef(null)
  const summaryRequest = useRef(0)
  const lastSummaryValidation = useRef(0)

  const revalidatePortfolioSummary = useCallback(async ({ force = false } = {}) => {
    const now = Date.now()
    if (!force && now - lastSummaryValidation.current < 60_000) return false
    lastSummaryValidation.current = now
    const requestId = ++summaryRequest.current

    try {
      const response = await getPortfolioSummary()
      if (requestId !== summaryRequest.current) return false
      const data = normalizePortfolioSummary(response.data?.data ?? null)
      setSummary(data)
      writeUserCache(CACHE_KEY_REALTIME, userId, data)
      setLastUpdated(saveCacheTime(userId))
      return true
    } catch {
      return false
    }
  }, [userId])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    if (ensureDashboardCacheVersion()) setLastUpdated(null)

    try {
      const portfolioResponse = await getPortfolio().catch(() => null)
      if (!portfolioResponse) {
        setPortfolio([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
        return
      }

      const rawPortfolio = portfolioResponse.data?.data
      const nextPortfolio = Array.isArray(rawPortfolio) ? rawPortfolio : []
      setPortfolio(nextPortfolio)
      setTargetWeights(targetWeightsFromPortfolio(nextPortfolio))

      const cachedSummary = readUserCache(CACHE_KEY_REALTIME, userId)
      const cachedHerd = readUserCache(CACHE_KEY_HERD, userId)
      const hasFreshHerdCache = Boolean(cachedHerd && isDashboardCacheFresh(userId))

      if (cachedSummary) setSummary(cachedSummary)
      if (hasFreshHerdCache) setHerdMap(herdStocksToMap(cachedHerd.stocks))

      const [, herdResult] = await Promise.allSettled([
        revalidatePortfolioSummary({ force: true }),
        hasFreshHerdCache
          ? Promise.resolve(null)
          : getPortfolioObservations(nextPortfolio),
      ])
      if (!hasFreshHerdCache) {
        const herdData = herdResult.status === 'fulfilled'
          ? observationResponseToCacheData(herdResult.value)
          : null
        setHerdMap(herdStocksToMap(herdData?.stocks))
        if (herdData) {
          writeUserCache(CACHE_KEY_HERD, userId, herdData)
          saveCacheTime(userId, CACHE_KEY_HERD_TIME)
        }
      }

      getCashBalance()
        .then((response) => {
          const amount = Number(response.data?.data?.cashAmount ?? 0)
          setCashBalance(amount)
          setCashDraft(amount > 0 ? String(amount) : '')
          setSummary((previous) => withCash(previous, amount))
        })
        .catch(() => setCashBalance(0))
    } finally {
      setLoading(false)
    }
  }, [revalidatePortfolioSummary, setTargetWeights, userId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    const revalidateOnReturn = () => {
      if (document.visibilityState !== 'visible') return
      revalidatePortfolioSummary()
      fetchDataStatus()
    }
    window.addEventListener('focus', revalidateOnReturn)
    document.addEventListener('visibilitychange', revalidateOnReturn)
    return () => {
      window.removeEventListener('focus', revalidateOnReturn)
      document.removeEventListener('visibilitychange', revalidateOnReturn)
    }
  }, [fetchDataStatus, revalidatePortfolioSummary])

  useEffect(() => () => {
    if (refreshNoticeTimer.current) clearTimeout(refreshNoticeTimer.current)
  }, [])

  const handleRefresh = useCallback(async () => {
    const priceRequestId = ++summaryRequest.current
    lastSummaryValidation.current = Date.now()
    setRefreshing(true)
    if (refreshNoticeTimer.current) clearTimeout(refreshNoticeTimer.current)
    setRefreshNotice('현재가 조회 · HERD DB 조회 · SPY 확인 중')

    try {
      const [priceResult, herdResult, spyResult] = await Promise.allSettled([
        getPortfolioRealtime(),
        getPortfolioObservations(portfolio),
        getHerdObservation('SPY'),
      ])

      if (priceResult.status === 'fulfilled') {
        const data = withCash(
          normalizePortfolioSummary(priceResult.value.data?.data ?? null),
          cashBalance,
        )
        if (priceRequestId === summaryRequest.current) {
          setSummary(data)
          writeUserCache(CACHE_KEY_REALTIME, userId, data)
          setLastUpdated(saveCacheTime(userId))
        }
      }

      if (herdResult.status === 'fulfilled') {
        const herdData = observationResponseToCacheData(herdResult.value)
        setHerdMap(herdStocksToMap(herdData?.stocks))
        writeUserCache(CACHE_KEY_HERD, userId, herdData)
        saveCacheTime(userId, CACHE_KEY_HERD_TIME)
      }

      if (spyResult.status === 'fulfilled') {
        updateSpyData(spyResult.value.data?.data ?? null)
      }

      setRefreshNotice(refreshResultText(priceResult, herdResult, spyResult))
      refreshNoticeTimer.current = setTimeout(() => setRefreshNotice(null), 3200)
    } finally {
      setRefreshing(false)
    }
  }, [cashBalance, portfolio, updateSpyData, userId])

  return {
    portfolio,
    setPortfolio,
    summary,
    setSummary,
    herdMap,
    loading,
    error,
    refreshing,
    refreshNotice,
    setRefreshNotice,
    lastUpdated,
    cashBalance,
    setCashBalance,
    cashDraft,
    setCashDraft,
    fetchData,
    handleRefresh,
  }
}
