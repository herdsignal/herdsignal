import { describe, expect, it } from 'vitest'
import {
  CACHE_KEY_HERD,
  CACHE_KEY_HERD_TIME,
  CACHE_KEY_REALTIME,
  CACHE_KEY_TIME,
  DASHBOARD_CACHE_TTL_MS,
  clearPortfolioCaches,
  isDashboardCacheFresh,
  userCacheKey,
} from './dashboardModel'

const USER_ID = 'user-1'

describe('dashboard cache policy', () => {
  it('expires stale portfolio data', () => {
    const now = Date.now()
    localStorage.setItem(userCacheKey(CACHE_KEY_HERD_TIME, USER_ID), new Date(now - DASHBOARD_CACHE_TTL_MS - 1).toISOString())

    expect(isDashboardCacheFresh(USER_ID, now)).toBe(false)
  })

  it('accepts a complete cache inside the TTL', () => {
    const now = Date.now()
    localStorage.setItem(userCacheKey(CACHE_KEY_HERD_TIME, USER_ID), new Date(now - 1_000).toISOString())

    expect(isDashboardCacheFresh(USER_ID, now)).toBe(true)
  })

  it('invalidates the related cache entries together', () => {
    localStorage.setItem(userCacheKey(CACHE_KEY_REALTIME, USER_ID), '{}')
    localStorage.setItem(userCacheKey(CACHE_KEY_HERD, USER_ID), '{}')
    localStorage.setItem(userCacheKey(CACHE_KEY_TIME, USER_ID), new Date().toISOString())

    clearPortfolioCaches(USER_ID)

    expect(localStorage.getItem(userCacheKey(CACHE_KEY_REALTIME, USER_ID))).toBeNull()
    expect(localStorage.getItem(userCacheKey(CACHE_KEY_HERD, USER_ID))).toBeNull()
    expect(localStorage.getItem(userCacheKey(CACHE_KEY_TIME, USER_ID))).toBeNull()
  })

  it('isolates portfolio caches by authenticated user', () => {
    localStorage.setItem(userCacheKey(CACHE_KEY_REALTIME, 'user-1'), '{"owner":1}')
    localStorage.setItem(userCacheKey(CACHE_KEY_REALTIME, 'user-2'), '{"owner":2}')

    clearPortfolioCaches('user-1')

    expect(localStorage.getItem(userCacheKey(CACHE_KEY_REALTIME, 'user-1'))).toBeNull()
    expect(localStorage.getItem(userCacheKey(CACHE_KEY_REALTIME, 'user-2'))).toBe('{"owner":2}')
  })
})
