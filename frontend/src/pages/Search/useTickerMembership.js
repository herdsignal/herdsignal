import { useCallback, useEffect, useState } from 'react'
import {
  addToPortfolio,
  addToWatchlist,
  getPortfolio,
  getWatchlist,
} from '../../api/herdApi'
import { clearPortfolioCaches } from '../../features/portfolio/portfolioCache'

export function useTickerMembership({ selectedTicker, userId, onPortfolioAdded }) {
  const [portfolioTickers, setPortfolioTickers] = useState(new Set())
  const [watchlistTickers, setWatchlistTickers] = useState(new Set())
  const [portfolioStatus, setPortfolioStatus] = useState('idle')
  const [watchlistStatus, setWatchlistStatus] = useState('idle')
  const [addError, setAddError] = useState('')

  useEffect(() => {
    let active = true
    Promise.allSettled([getPortfolio(), getWatchlist()]).then(([portfolio, watchlist]) => {
      if (!active) return
      if (portfolio.status === 'fulfilled') {
        const list = portfolio.value.data?.data ?? []
        setPortfolioTickers(new Set(list.map((item) => item.ticker)))
      }
      if (watchlist.status === 'fulfilled') {
        const list = watchlist.value.data?.data ?? []
        setWatchlistTickers(new Set(list.map((item) => item.ticker)))
      }
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    setPortfolioStatus(
      selectedTicker && portfolioTickers.has(selectedTicker) ? 'exists' : 'idle'
    )
    setWatchlistStatus(
      selectedTicker && watchlistTickers.has(selectedTicker) ? 'exists' : 'idle'
    )
    setAddError('')
  }, [selectedTicker, portfolioTickers, watchlistTickers])

  const handleAddPortfolio = useCallback(async (ticker) => {
    if (portfolioStatus !== 'idle') return
    setAddError('')
    setPortfolioStatus('loading')
    try {
      await addToPortfolio(ticker)
      setPortfolioStatus('added')
      setPortfolioTickers((current) => new Set([...current, ticker]))
      clearPortfolioCaches(userId)
      onPortfolioAdded?.(ticker)
    } catch (error) {
      setPortfolioStatus(error.response?.status === 409 ? 'exists' : 'idle')
      if (error.response?.status !== 409) {
        setAddError(error.response?.data?.message ?? '종목을 추가할 수 없습니다.')
      }
    }
  }, [portfolioStatus, userId, onPortfolioAdded])

  const handleAddWatchlist = useCallback(async (ticker) => {
    if (watchlistStatus !== 'idle') return
    setAddError('')
    setWatchlistStatus('loading')
    try {
      await addToWatchlist(ticker)
      setWatchlistStatus('added')
      setWatchlistTickers((current) => new Set([...current, ticker]))
    } catch (error) {
      setWatchlistStatus(error.response?.status === 409 ? 'exists' : 'idle')
      if (error.response?.status !== 409) {
        setAddError(error.response?.data?.message ?? '종목을 추가할 수 없습니다.')
      }
    }
  }, [watchlistStatus])

  return {
    portfolioTickers,
    watchlistTickers,
    portfolioStatus,
    watchlistStatus,
    addError,
    handleAddPortfolio,
    handleAddWatchlist,
  }
}
