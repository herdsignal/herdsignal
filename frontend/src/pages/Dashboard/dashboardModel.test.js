import { describe, expect, it } from 'vitest'
import {
  CACHE_KEY_HERD,
  CACHE_KEY_REALTIME,
  CACHE_KEY_TIME,
  DASHBOARD_CACHE_TTL_MS,
  clearPortfolioCaches,
  isDashboardCacheFresh,
} from './dashboardModel'

describe('dashboard cache policy', () => {
  it('expires stale portfolio data', () => {
    const now = Date.now()
    localStorage.setItem(CACHE_KEY_TIME, new Date(now - DASHBOARD_CACHE_TTL_MS - 1).toISOString())

    expect(isDashboardCacheFresh(now)).toBe(false)
  })

  it('accepts a complete cache inside the TTL', () => {
    const now = Date.now()
    localStorage.setItem(CACHE_KEY_TIME, new Date(now - 1_000).toISOString())

    expect(isDashboardCacheFresh(now)).toBe(true)
  })

  it('invalidates the related cache entries together', () => {
    localStorage.setItem(CACHE_KEY_REALTIME, '{}')
    localStorage.setItem(CACHE_KEY_HERD, '{}')
    localStorage.setItem(CACHE_KEY_TIME, new Date().toISOString())

    clearPortfolioCaches()

    expect(localStorage.getItem(CACHE_KEY_REALTIME)).toBeNull()
    expect(localStorage.getItem(CACHE_KEY_HERD)).toBeNull()
    expect(localStorage.getItem(CACHE_KEY_TIME)).toBeNull()
  })
})
