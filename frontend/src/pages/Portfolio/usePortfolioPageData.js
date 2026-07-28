import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { fetchExchangeRate, formatKRW } from '../../utils/currency'
import { targetWeightsFromPortfolio } from '../../utils/portfolioTools'
import { fmtUSD } from './portfolioPresentation'
import { usePortfolioAssetHistory } from './usePortfolioAssetHistory'
import { usePortfolioData } from './usePortfolioData'
import { usePortfolioMutations } from './usePortfolioMutations'
import {
  buildPortfolioRows,
  portfolioTodayChange,
  sortPortfolioRows,
} from './portfolioModel'

const CURRENCY_STORAGE_KEY = 'herdsignal_currency'
const SORT_STORAGE_KEY = 'herdsignal_portfolio_lens_sort'
const PRIVACY_STORAGE_KEY = 'herdsignal_portfolio_privacy'

export function usePortfolioPageData({
  assetHistoryInitiallyOpen = true,
  enabled = true,
} = {}) {
  const { user } = useAuth()
  const userId = user?.id
  const [, setTargetWeights] = useState({})
  const [modalTicker, setModalTicker] = useState(null)
  const [currencyMode, setCurrencyMode] = useState(
    () => localStorage.getItem(CURRENCY_STORAGE_KEY) || 'KRW',
  )
  const [sortBy, setSortBy] = useState(
    () => localStorage.getItem(SORT_STORAGE_KEY) || 'weight',
  )
  const [privacyMode, setPrivacyMode] = useState(
    () => localStorage.getItem(PRIVACY_STORAGE_KEY) !== 'visible',
  )
  const [exchangeRate, setExchangeRate] = useState(null)

  const data = usePortfolioData({
    userId,
    setTargetWeights,
    enabled,
  })
  const history = usePortfolioAssetHistory(data.summary, data.cashBalance, {
    initiallyOpen: assetHistoryInitiallyOpen,
  })
  const priceMap = useMemo(() => Object.fromEntries(
    (data.summary?.stocks ?? []).map((stock) => [stock.ticker, stock]),
  ), [data.summary])
  const mutations = usePortfolioMutations({
    userId,
    portfolio: data.portfolio,
    setPortfolio: data.setPortfolio,
    setSummary: data.setSummary,
    priceMap,
    cashBalance: data.cashBalance,
    setCashBalance: data.setCashBalance,
    cashDraft: data.cashDraft,
    setCashDraft: data.setCashDraft,
    setTargetWeights,
    modalTicker,
    setModalTicker,
    fetchData: data.fetchData,
    assetPanelOpen: true,
    fetchAssetHistory: history.fetchAssetHistory,
    setRefreshNotice: data.setRefreshNotice,
  })

  useEffect(() => {
    let active = true
    fetchExchangeRate().then((rate) => {
      if (active) setExchangeRate(rate)
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    setTargetWeights(targetWeightsFromPortfolio(data.portfolio))
  }, [data.portfolio, setTargetWeights])

  const rows = useMemo(
    () => buildPortfolioRows(data.portfolio, data.summary, data.herdMap),
    [data.herdMap, data.portfolio, data.summary],
  )
  const sortedRows = useMemo(
    () => sortPortfolioRows(rows, sortBy),
    [rows, sortBy],
  )
  const todayChange = useMemo(
    () => portfolioTodayChange(data.summary),
    [data.summary],
  )
  const displayAmount = useCallback((usdValue) => {
    if (usdValue == null) return '—'
    if (privacyMode) return '••••••'
    if (currencyMode === 'KRW' && exchangeRate != null) {
      return formatKRW(usdValue, exchangeRate)
    }
    return fmtUSD(usdValue)
  }, [currencyMode, exchangeRate, privacyMode])

  const displaySignedAmount = useCallback((usdValue) => {
    if (usdValue == null) return '—'
    const numeric = Number(usdValue)
    if (!Number.isFinite(numeric)) return '—'
    const absolute = displayAmount(Math.abs(numeric))
    return `${numeric >= 0 ? '+' : '-'}${absolute}`
  }, [displayAmount])

  const selectCurrency = useCallback((mode) => {
    setCurrencyMode(mode)
    localStorage.setItem(CURRENCY_STORAGE_KEY, mode)
  }, [])

  const selectSort = useCallback((value) => {
    setSortBy(value)
    localStorage.setItem(SORT_STORAGE_KEY, value)
  }, [])

  const togglePrivacyMode = useCallback(() => {
    setPrivacyMode((hidden) => {
      const next = !hidden
      localStorage.setItem(PRIVACY_STORAGE_KEY, next ? 'hidden' : 'visible')
      return next
    })
  }, [])

  const refresh = useCallback(async () => {
    await data.handleRefresh()
    await history.fetchAssetHistory()
  }, [data, history])

  return {
    ...data,
    ...history,
    ...mutations,
    modalTicker,
    setModalTicker,
    currencyMode,
    exchangeRate,
    selectCurrency,
    privacyMode,
    togglePrivacyMode,
    sortBy,
    selectSort,
    rows,
    sortedRows,
    todayChange,
    displayAmount,
    displaySignedAmount,
    refresh,
  }
}
