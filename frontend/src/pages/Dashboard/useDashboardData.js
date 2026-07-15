import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  getPortfolio,
  getPortfolioSummary,
  getPortfolioRealtime,
  getPortfolioHerd,
  getStockHerd,
  getPortfolioHistory,
  getCashBalance,
  updateCashBalance,
  getSignalJournal,
  removeFromPortfolio,
} from '../../api/herdApi'
import { formatKRW } from '../../utils/currency'
import { buildPortfolioAlerts } from '../../utils/alertRules'
import {
  portfolioRows,
  portfolioRiskWarnings,
  readTargetWeights,
  writeTargetWeights,
} from '../../utils/portfolioTools'
import { summarizeSignalJournal } from '../../utils/signalJournal'
import { useAuth } from '../../auth/AuthContext'
import {
  API_HOST,
  CACHE_KEY_REALTIME,
  CACHE_KEY_HERD,
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_TIME,
  CACHE_KEY_PORTFOLIO_SORT,
  ASSET_HISTORY_PERIODS,
  readUserCache,
  writeUserCache,
  userCacheKey,
  ensureDashboardCacheVersion,
  normalizePortfolioSummary,
  saveCacheTime,
  isDashboardCacheFresh,
  clearPortfolioCaches,
  buildPositionAction,
  queuePriority,
  sortPortfolioItems,
  refreshResultText,
  fmtAxisDate,
  normalizeHistoryPoint,
  currentAssetPoint,
  mergeCurrentAssetPoint,
} from './dashboardModel'
import { useDashboardMarketData } from './useDashboardMarketData'

export function useDashboardData() {

  const { user } = useAuth()
  const userId = user?.id

  const [portfolio,      setPortfolio]      = useState([])
  const [summary,        setSummary]        = useState(null)
  const [herdMap,        setHerdMap]        = useState({})
  const market = useDashboardMarketData()
  const { exchangeRate, updateSpyData } = market
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  const [modalTicker,    setModalTicker]    = useState(null)
  const [deletingTicker, setDeletingTicker] = useState(null)
  const [refreshing,     setRefreshing]     = useState(false)
  const [refreshNotice,  setRefreshNotice]  = useState(null)
  /*
   * 마지막 캐시 저장 시각 — localStorage 'hs_cache_time'에서 초기화.
   * 캐시 없으면 null (헤더에 업데이트 시각 미표시).
   */
  const [lastUpdated,    setLastUpdated]    = useState(() => {
    const t = localStorage.getItem(userCacheKey(CACHE_KEY_TIME, userId))
    return t ? new Date(t) : null
  })
  const [currencyMode,   setCurrencyMode]   = useState(
    () => localStorage.getItem('herdsignal_currency') || 'KRW'
  )
  const [editMode,       setEditMode]       = useState(false)
  const [portfolioSort,  setPortfolioSort]  = useState(
    () => localStorage.getItem(CACHE_KEY_PORTFOLIO_SORT) || 'action'
  )
  const [targetWeights,  setTargetWeights]  = useState(() => readTargetWeights())
  const [cashBalance,    setCashBalance]    = useState(0)
  const [cashDraft,      setCashDraft]      = useState('')
  const [cashSaving,     setCashSaving]     = useState(false)
  const [assetPanelOpen, setAssetPanelOpen] = useState(false)
  const [assetHistoryPeriod, setAssetHistoryPeriod] = useState('year')
  const [assetHistory,   setAssetHistory]   = useState([])
  const [assetHistoryLoading, setAssetHistoryLoading] = useState(false)
  const [assetHistoryError, setAssetHistoryError] = useState(null)
  const [signalLogs,     setSignalLogs]     = useState([])
  const refreshNoticeTimer = useRef(null)
  const assetHistoryRequest = useRef(0)
  const summaryRequest = useRef(0)
  const lastSummaryValidation = useRef(0)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /** DB 종가 요약을 재검증한다. 캐시는 화면 선표시용이며 성공한 최신 요청만 반영한다. */
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

  /* ── 포트폴리오 데이터 로딩 (캐시 우선) ── */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    if (ensureDashboardCacheVersion()) {
      setLastUpdated(null)
    }
    try {
      /*
       * (1) 종목 목록 — 항상 최신 조회.
       *     avgPrice/quantity는 사용자가 언제든 변경할 수 있으므로 캐시 사용 안 함.
       */
      const portfolioRes = await getPortfolio().catch(() => null)
      if (portfolioRes) {
        const raw = portfolioRes.data?.data
        setPortfolio(Array.isArray(raw) ? raw : [])
      } else {
        setPortfolio([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
        return
      }

      /*
       * (2) 가격 / HERD 점수 — 사용자별 localStorage 캐시를 먼저 표시.
       *     가격은 항상 DB 최신값으로 재검증하고 HERD만 30분 캐시한다.
       */
      const cachedSummary = readUserCache(CACHE_KEY_REALTIME, userId)
      const cachedHerd    = readUserCache(CACHE_KEY_HERD, userId)
      const hasFreshHerdCache = Boolean(cachedHerd && isDashboardCacheFresh(userId))

      // 가격 캐시는 API 응답을 기다리는 동안 즉시 표시한다.
      if (cachedSummary) setSummary(cachedSummary)
      if (hasFreshHerdCache) {
        const map = {}
        cachedHerd.stocks?.forEach((h) => { map[h.ticker] = h })
        setHerdMap(map)
      }

      // DB 가격 요약은 캐시 유무와 관계없이 진입 시 항상 최신값을 확인한다.
      const [, herdRes] = await Promise.allSettled([
        revalidatePortfolioSummary({ force: true }),
        hasFreshHerdCache ? Promise.resolve(null) : getPortfolioHerd(),
      ])
      if (!hasFreshHerdCache) {
        const map = {}
        if (herdRes.status === 'fulfilled') {
          const herdData = herdRes.value?.data?.data ?? null
          const herdStocks = herdData?.stocks ?? []
          herdStocks.forEach((h) => { map[h.ticker] = h })
          writeUserCache(CACHE_KEY_HERD, userId, herdData)
          saveCacheTime(userId, CACHE_KEY_HERD_TIME)
        }
        setHerdMap(map)
      }

      getCashBalance()
        .then((res) => {
          const amount = Number(res.data?.data?.cashAmount ?? 0)
          setCashBalance(amount)
          setCashDraft(amount > 0 ? String(amount) : '')
          setSummary(prev => prev
            ? {
                ...prev,
                cash_balance: amount,
                total_value: Number(prev.invested_value ?? prev.total_value ?? 0) + amount,
                total_asset_value: Number(prev.invested_value ?? prev.total_value ?? 0) + amount,
              }
            : prev
          )
        })
        .catch(() => {
          setCashBalance(0)
        })
    } finally {
      setLoading(false)
    }
  }, [userId, revalidatePortfolioSummary])

  const fetchAssetHistory = useCallback(async () => {
    const requestId = ++assetHistoryRequest.current
    setAssetHistoryLoading(true)
    setAssetHistoryError(null)
    try {
      const res = await getPortfolioHistory(assetHistoryPeriod)
      const points = (res.data?.data?.points ?? []).map(normalizeHistoryPoint)
      if (requestId === assetHistoryRequest.current) setAssetHistory(points)
    } catch {
      if (requestId === assetHistoryRequest.current) {
        setAssetHistoryError('자산 히스토리를 불러올 수 없습니다.')
      }
    } finally {
      if (requestId === assetHistoryRequest.current) setAssetHistoryLoading(false)
    }
  }, [assetHistoryPeriod])

  useEffect(() => {
    if (assetPanelOpen) fetchAssetHistory()
  }, [assetPanelOpen, fetchAssetHistory])

  useEffect(() => { fetchData() }, [fetchData])

  useEffect(() => {
    const revalidateOnReturn = () => {
      if (document.visibilityState === 'visible') revalidatePortfolioSummary()
    }
    window.addEventListener('focus', revalidateOnReturn)
    document.addEventListener('visibilitychange', revalidateOnReturn)
    return () => {
      window.removeEventListener('focus', revalidateOnReturn)
      document.removeEventListener('visibilitychange', revalidateOnReturn)
    }
  }, [revalidatePortfolioSummary])

  useEffect(() => {
    const syncSignalLogs = () => {
      getSignalJournal()
        .then((res) => setSignalLogs(res.data?.data ?? []))
        .catch(() => setSignalLogs([]))
    }
    syncSignalLogs()
    window.addEventListener('focus', syncSignalLogs)
    return () => {
      window.removeEventListener('focus', syncSignalLogs)
    }
  }, [])

  useEffect(() => () => {
    if (refreshNoticeTimer.current) clearTimeout(refreshNoticeTimer.current)
  }, [])

  /* ticker → 현재가 데이터 맵 (Python snake_case) */
  const priceMap = useMemo(() => {
    const map = {}
    summary?.stocks?.forEach((s) => { map[s.ticker] = s })
    return map
  }, [summary])

  /* 통화 모드 전환 — localStorage에 저장 */
  const handleCurrencyToggle = useCallback((mode) => {
    setCurrencyMode(mode)
    localStorage.setItem('herdsignal_currency', mode)
  }, [])

  /**
   * USD 금액 → 통화 모드에 맞게 표시.
   * 원화: "22,515,837원" / 달러: "$14,518.01"
   */
  const displayAmount = useCallback((usdValue) => {
    if (usdValue == null) return '—'
    if (currencyMode === 'KRW' && exchangeRate != null) {
      return formatKRW(usdValue, exchangeRate)
    }
    return fmtUSD(usdValue)
  }, [currencyMode, exchangeRate])

  /**
   * USD 손익 → 통화 모드에 맞게 부호 포함 표시.
   * 원화: "+3,139,172원" / 달러: "+$1,234.56"
   */
  const displayPnl = useCallback((usdPnl) => {
    if (usdPnl == null) return '—'
    const n    = Number(usdPnl)
    const sign = n >= 0 ? '+' : ''
    if (currencyMode === 'KRW' && exchangeRate != null) {
      const krw = Math.round(n * exchangeRate)
      return `${sign}${krw.toLocaleString('ko-KR')}원`
    }
    const absStr = Math.abs(n).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    return `${n < 0 ? '-' : '+'}$${absStr}`
  }, [currencyMode, exchangeRate])

  /*
   * 수동 새로고침 — yfinance 현재가 + DB HERD 데이터를 재조회 후 캐시 갱신.
   * getPortfolio()와 SPY 3년 히스토리는 제외한다.
   * 종목 목록은 추가/삭제 시에만 바뀌고, 히스토리는 최초 로딩 캐시로 충분하다.
   */
  const handleRefresh = useCallback(async () => {
    const priceRequestId = ++summaryRequest.current
    lastSummaryValidation.current = Date.now()
    setRefreshing(true)
    if (refreshNoticeTimer.current) clearTimeout(refreshNoticeTimer.current)
    setRefreshNotice('현재가 조회 · HERD DB 조회 · SPY 확인 중')
    try {
      const [priceRes, herdRes, spyRes] = await Promise.allSettled([
        getPortfolioRealtime(),
        getPortfolioHerd(),
        getStockHerd('SPY'),
      ])

      if (priceRes.status === 'fulfilled') {
        const data = normalizePortfolioSummary(priceRes.value.data?.data ?? null)
        if (data) {
          data.cash_balance = cashBalance
          data.total_value = Number(data.invested_value ?? data.total_value ?? 0) + Number(cashBalance ?? 0)
          data.total_asset_value = data.total_value
        }
        if (priceRequestId === summaryRequest.current) {
          setSummary(data)
          writeUserCache(CACHE_KEY_REALTIME, userId, data)
          setLastUpdated(saveCacheTime(userId))
        }
      }

      if (herdRes.status === 'fulfilled') {
        const map = {}
        const herdData = herdRes.value?.data?.data ?? null
        const herdStocks = herdData?.stocks ?? []
        herdStocks.forEach((h) => { map[h.ticker] = h })
        writeUserCache(CACHE_KEY_HERD, userId, herdData)
        saveCacheTime(userId, CACHE_KEY_HERD_TIME)
        setHerdMap(map)
      }

      if (spyRes.status === 'fulfilled') {
        const data = spyRes.value.data?.data ?? null
        updateSpyData(data)
      }

      setRefreshNotice(refreshResultText(priceRes, herdRes, spyRes))
      refreshNoticeTimer.current = setTimeout(() => {
        setRefreshNotice(null)
      }, 3200)
    } finally {
      setRefreshing(false)
    }
  }, [cashBalance, updateSpyData, userId])

  const handleCashSave = useCallback(async () => {
    const amount = Number(cashDraft || 0)
    if (!Number.isFinite(amount) || amount < 0 || cashSaving) return

    setCashSaving(true)
    try {
      const res = await updateCashBalance(amount)
      const saved = Number(res.data?.data?.cashAmount ?? amount)
      setCashBalance(saved)
      setCashDraft(saved > 0 ? String(saved) : '')
      setSummary(prev => {
        if (!prev) return prev
        const investedValue = Number(prev.invested_value ?? prev.total_value ?? 0)
        const next = {
          ...prev,
          cash_balance: saved,
          total_value: investedValue + saved,
          total_asset_value: investedValue + saved,
        }
        writeUserCache(CACHE_KEY_REALTIME, userId, next)
        return next
      })
      if (assetPanelOpen) fetchAssetHistory()
      setRefreshNotice('현금 보유액을 저장했습니다.')
    } catch {
      setRefreshNotice('현금 보유액 저장에 실패했습니다. 입력값과 서버 상태를 확인해주세요.')
    } finally {
      setCashSaving(false)
    }
  }, [cashDraft, cashSaving, assetPanelOpen, fetchAssetHistory, userId])

  /* 포트폴리오 종목 삭제 — API 성공 시 로컬 상태 즉시 제거 (낙관적 업데이트) */
  async function handleDelete(e, ticker) {
    e.stopPropagation()
    if (deletingTicker) return
    setDeletingTicker(ticker)
    try {
      await removeFromPortfolio(ticker)
      setPortfolio(prev => prev.filter(item => item.ticker !== ticker))
      setTargetWeights(prev => {
        const next = { ...prev }
        delete next[ticker]
        writeTargetWeights(next)
        return next
      })
      clearPortfolioCaches(userId)
      await fetchData()
    } catch {
      setRefreshNotice(`${ticker} 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.`)
    } finally {
      setDeletingTicker(null)
    }
  }

  function handlePortfolioSortChange(mode) {
    setPortfolioSort(mode)
    localStorage.setItem(CACHE_KEY_PORTFOLIO_SORT, mode)
  }


  const signalJournalSummary = useMemo(
    () => summarizeSignalJournal(signalLogs),
    [signalLogs]
  )

  const recentSignalLogs = useMemo(
    () => signalLogs.slice(0, 3),
    [signalLogs]
  )

  /*
   * 모달 저장 완료 → 로컬 상태 즉시 업데이트 + localStorage 캐시 갱신.
   * summary는 항상 USD 단위로 저장. displayAmount/displayPnl이 통화 변환 담당.
   */
  const handleModalSaved = useCallback((newAvgPrice, newQty) => {
    const ticker = modalTicker

    setPortfolio(prev => prev.map(p =>
      p.ticker === ticker ? { ...p, avgPrice: newAvgPrice, quantity: newQty } : p
    ))

    const currentPrice = priceMap[ticker]?.current_price
    if (currentPrice != null) {
      const newMarketValue = currentPrice * newQty
      const newReturnPct   = (currentPrice - newAvgPrice) / newAvgPrice * 100

      setSummary(prev => {
        if (!prev) return prev

        const updatedStocks = (prev.stocks ?? []).map(s =>
          s.ticker === ticker
            ? { ...s, market_value: newMarketValue, return_pct: newReturnPct }
            : s
        )
        const oldMarketValue = priceMap[ticker]?.market_value ?? 0
        const newInvestedValue = (prev.invested_value ?? prev.total_value ?? 0) - oldMarketValue + newMarketValue
        const cash = Number(prev.cash_balance ?? cashBalance ?? 0)
        const oldStock       = portfolio.find(p => p.ticker === ticker)
        const oldCost        = (oldStock?.avgPrice ?? 0) * (oldStock?.quantity ?? 0)
        const newTotalCost   = (prev.total_cost ?? 0) - oldCost + newAvgPrice * newQty
        const newTotalReturnPct = newTotalCost > 0
          ? (newInvestedValue - newTotalCost) / newTotalCost * 100
          : 0

        const next = {
          ...prev,
          stocks:           updatedStocks,
          invested_value:   newInvestedValue,
          total_value:      newInvestedValue + cash,
          total_asset_value: newInvestedValue + cash,
          total_cost:       newTotalCost,
          total_return_pct: newTotalReturnPct,
        }
        /* 캐시도 함께 갱신 — 다음 방문 시 수정된 수익률 표시 */
        writeUserCache(CACHE_KEY_REALTIME, userId, next)
        return next
      })
    } else {
      fetchData()
    }

    setModalTicker(null)
  }, [modalTicker, priceMap, portfolio, fetchData, cashBalance, userId])

  const modalStock = portfolio.find((p) => p.ticker === modalTicker)
  const rows = useMemo(
    () => portfolioRows(portfolio, summary, herdMap, targetWeights),
    [portfolio, summary, herdMap, targetWeights]
  )
  const sortedPortfolio = useMemo(
    () => sortPortfolioItems(portfolio, rows, herdMap, portfolioSort),
    [portfolio, rows, herdMap, portfolioSort]
  )
  const riskWarnings = useMemo(
    () => portfolioRiskWarnings(rows, summary),
    [rows, summary]
  )
  const portfolioAlerts = useMemo(
    () => buildPortfolioAlerts(rows, riskWarnings),
    [rows, riskWarnings]
  )
  const actionQueueCards = useMemo(() => {
    const rowMap = new Map(rows.map((row) => [row.ticker, row]))
    return sortedPortfolio
      .map((item) => {
        const herd = herdMap[item.ticker]
        const row = rowMap.get(item.ticker)
        if (!herd || !row) return null
        const action = buildPositionAction(herd, row)
        const score = Math.round(herd.herdV4 ?? herd.herdScore ?? 0)
        const stage = herd.herdStage?.startsWith('Herd ')
          ? herd.herdStage.slice(5)
          : herd.herdStage ?? 'Calm'
        return {
          ticker: item.ticker,
          herd,
          row,
          action,
          score,
          stage,
          price: priceMap[item.ticker],
          priority: queuePriority(action.code),
        }
      })
      .filter(Boolean)
      .sort((a, b) => {
        if (a.priority !== b.priority) return a.priority - b.priority
        return Number(b.herd.actionScore ?? 0) - Number(a.herd.actionScore ?? 0)
      })
      .slice(0, 3)
  }, [sortedPortfolio, rows, herdMap, priceMap])
  const assetHistoryWithCurrent = useMemo(
    () => mergeCurrentAssetPoint(assetHistory, currentAssetPoint(summary, cashBalance)),
    [assetHistory, summary, cashBalance]
  )
  const assetChartHistory = assetHistoryWithCurrent
  const assetLatest = assetChartHistory.length > 0 ? assetChartHistory[assetChartHistory.length - 1] : null
  const assetFirst = assetChartHistory.length > 0 ? assetChartHistory[0] : null
  const assetStartValue = assetFirst?.totalAssetValue ?? null
  const investedStartValue = assetFirst?.investedValue ?? null
  const assetPeak = assetChartHistory.length > 0
    ? assetChartHistory.reduce((best, point) =>
        Number(point.totalAssetValue) > Number(best.totalAssetValue) ? point : best
      , assetChartHistory[0])
    : null
  const totalFlowPct = assetStartValue && assetLatest?.totalAssetValue
    ? (assetLatest.totalAssetValue / assetStartValue - 1) * 100
    : null
  const investedChangePct = investedStartValue && assetLatest?.investedValue
    ? (assetLatest.investedValue / investedStartValue - 1) * 100
    : null
  const assetDrawdownPct = assetPeak?.totalAssetValue && assetLatest?.totalAssetValue
    ? (assetLatest.totalAssetValue / assetPeak.totalAssetValue - 1) * 100
    : null
  const assetValues = assetChartHistory.flatMap((p) => [
    Number(p.totalAssetValue),
    Number(p.investedValue),
  ]).filter(Number.isFinite)
  if (assetStartValue) assetValues.push(assetStartValue)
  const assetMin = assetValues.length > 0 ? Math.min(...assetValues) : 0
  const assetMax = assetValues.length > 0 ? Math.max(...assetValues) : 1000
  const assetPadding = (assetMax - assetMin) * 0.08 || 100
  const assetYDomain = [Math.max(0, assetMin - assetPadding), assetMax + assetPadding]
  const assetPeriodLabel = ASSET_HISTORY_PERIODS.find((p) => p.value === assetHistoryPeriod)?.label ?? '선택 기간'
  const assetStartLabel = assetFirst?.date ? fmtAxisDate(assetFirst.date) : '—'

  function handleTargetWeightChange(ticker, value) {
    const next = { ...targetWeights }
    if (value === '') {
      delete next[ticker]
    } else {
      const n = Number(value)
      if (!Number.isFinite(n)) return
      next[ticker] = String(Math.min(100, Math.max(0, n)))
    }
    setTargetWeights(next)
    writeTargetWeights(next)
  }

  return {
    portfolio, summary, herdMap,
    ...market,
    loading, error,
    modalTicker, setModalTicker, deletingTicker,
    refreshing, refreshNotice, lastUpdated,
    currencyMode, editMode, setEditMode,
    portfolioSort, targetWeights,
    cashBalance, cashDraft, setCashDraft, cashSaving,
    assetPanelOpen, setAssetPanelOpen,
    assetHistoryPeriod, setAssetHistoryPeriod,
    assetHistoryLoading, assetHistoryError,
    today, fetchData, priceMap,
    handleCurrencyToggle, displayAmount, displayPnl,
    handleRefresh, handleCashSave, handleDelete,
    handlePortfolioSortChange,
    signalJournalSummary, recentSignalLogs,
    handleModalSaved, modalStock, rows, sortedPortfolio,
    riskWarnings, portfolioAlerts, actionQueueCards,
    assetChartHistory, assetLatest, assetFirst, assetStartValue,
    totalFlowPct, investedChangePct, assetDrawdownPct,
    assetYDomain, assetPeriodLabel, assetStartLabel,
    handleTargetWeightChange,
  }
}
