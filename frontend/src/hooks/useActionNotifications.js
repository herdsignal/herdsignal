import { useEffect, useMemo, useState } from 'react'
import { getPortfolioHerd, getWatchlistHerd } from '../api/herdApi'
import { useAuth } from '../auth/AuthContext'
import {
  buildActionNotificationState,
  mergeTrackedStocks,
} from '../utils/actionNotifications'

const EMPTY_SUMMARY = { buy: 0, hold: 0, reduce: 0, total: 0 }

function storageKey(userId) {
  return `herdsignal_action_notifications:${userId || 'local'}`
}

function readSnapshot(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || '{}')
  } catch {
    return {}
  }
}

export function useActionNotifications() {
  const { user } = useAuth()
  const [changes, setChanges] = useState([])
  const [summary, setSummary] = useState(EMPTY_SUMMARY)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const key = storageKey(user?.id)

    Promise.allSettled([getPortfolioHerd(), getWatchlistHerd()])
      .then(([portfolioResult, watchlistResult]) => {
        if (!active) return
        const portfolio = portfolioResult.status === 'fulfilled'
          ? portfolioResult.value.data?.data?.stocks ?? []
          : []
        const watchlist = watchlistResult.status === 'fulfilled'
          ? watchlistResult.value.data?.data?.stocks ?? []
          : []
        const items = mergeTrackedStocks(portfolio, watchlist)
        const next = buildActionNotificationState(items, readSnapshot(key))
        localStorage.setItem(key, JSON.stringify(next.snapshot))
        setChanges(next.changes)
        setSummary(next.summary)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => { active = false }
  }, [user?.id])

  return useMemo(() => ({
    changes,
    summary,
    loading,
  }), [changes, summary, loading])
}
