import { useCallback, useState } from 'react'
import { formatKRW } from '../../utils/currency'
import { CACHE_KEY_PORTFOLIO_SORT } from './dashboardCache'
import { fmtUSD } from './dashboardPresentation'

const CURRENCY_STORAGE_KEY = 'herdsignal_currency'

export function useDashboardPreferences(exchangeRate) {
  const [currencyMode, setCurrencyMode] = useState(
    () => localStorage.getItem(CURRENCY_STORAGE_KEY) || 'KRW'
  )
  const [portfolioSort, setPortfolioSort] = useState(
    () => localStorage.getItem(CACHE_KEY_PORTFOLIO_SORT) || 'action'
  )

  const handleCurrencyToggle = useCallback((mode) => {
    setCurrencyMode(mode)
    localStorage.setItem(CURRENCY_STORAGE_KEY, mode)
  }, [])

  const handlePortfolioSortChange = useCallback((mode) => {
    setPortfolioSort(mode)
    localStorage.setItem(CACHE_KEY_PORTFOLIO_SORT, mode)
  }, [])

  const displayAmount = useCallback((usdValue) => {
    if (usdValue == null) return '—'
    if (currencyMode === 'KRW' && exchangeRate != null) {
      return formatKRW(usdValue, exchangeRate)
    }
    return fmtUSD(usdValue)
  }, [currencyMode, exchangeRate])

  const displayPnl = useCallback((usdPnl) => {
    if (usdPnl == null) return '—'
    const number = Number(usdPnl)
    const sign = number >= 0 ? '+' : ''
    if (currencyMode === 'KRW' && exchangeRate != null) {
      return `${sign}${Math.round(number * exchangeRate).toLocaleString('ko-KR')}원`
    }
    const absolute = Math.abs(number).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    return `${number < 0 ? '-' : '+'}$${absolute}`
  }, [currencyMode, exchangeRate])

  return {
    currencyMode,
    portfolioSort,
    handleCurrencyToggle,
    handlePortfolioSortChange,
    displayAmount,
    displayPnl,
  }
}
