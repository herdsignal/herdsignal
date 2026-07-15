import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDashboardData } from './useDashboardData'
import * as api from '../../api/herdApi'
import {
  CACHE_KEY_REALTIME,
  CACHE_KEY_TIME,
  CACHE_KEY_VERSION,
  DASHBOARD_CACHE_VERSION,
  userCacheKey,
} from './dashboardModel'

const USER_ID = 'user-1'

vi.mock('../../api/herdApi', () => ({
  getPortfolio: vi.fn(),
  getPortfolioSummary: vi.fn(),
  getPortfolioRealtime: vi.fn(),
  getPortfolioHerd: vi.fn(),
  getStockHerd: vi.fn(),
  getSpyHerdHistory: vi.fn(),
  getPortfolioHistory: vi.fn(),
  getCashBalance: vi.fn(),
  updateCashBalance: vi.fn(),
  getSignalJournal: vi.fn(),
  removeFromPortfolio: vi.fn(),
}))

vi.mock('../../utils/currency', () => ({
  fetchExchangeRate: vi.fn().mockResolvedValue(null),
  formatKRW: vi.fn((value) => String(value)),
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { authenticated: true, id: 'user-1' } }),
}))

function response(data) {
  return Promise.resolve({ data: { data } })
}

beforeEach(() => {
  api.getPortfolio.mockReturnValue(response([]))
  api.getPortfolioSummary.mockReturnValue(response({ totalValue: 100 }))
  api.getPortfolioHerd.mockReturnValue(response({ stocks: [{ ticker: 'AAPL', herdScore: 40 }] }))
  api.getStockHerd.mockReturnValue(response({ ticker: 'SPY', herdScore: 50 }))
  api.getSpyHerdHistory.mockReturnValue(response({ points: [] }))
  api.getCashBalance.mockReturnValue(response({ cashAmount: 0 }))
  api.getSignalJournal.mockReturnValue(response([]))
})

afterEach(() => cleanup())

describe('useDashboardData cache recovery', () => {
  it('refetches both resources when only the summary cache exists', async () => {
    localStorage.setItem(CACHE_KEY_VERSION, DASHBOARD_CACHE_VERSION)
    localStorage.setItem(userCacheKey(CACHE_KEY_REALTIME, USER_ID), JSON.stringify({ total_value: 999 }))
    localStorage.setItem(userCacheKey(CACHE_KEY_TIME, USER_ID), new Date().toISOString())

    const { result } = renderHook(() => useDashboardData())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(api.getPortfolioSummary).toHaveBeenCalledTimes(1)
    expect(api.getPortfolioHerd).toHaveBeenCalledTimes(1)
    expect(result.current.herdMap.AAPL?.herdScore).toBe(40)
    expect(result.current).toHaveProperty('assetStartValue', 100)
  })

  it('revalidates the portfolio summary even when a cached summary exists', async () => {
    localStorage.setItem(CACHE_KEY_VERSION, DASHBOARD_CACHE_VERSION)
    localStorage.setItem(userCacheKey(CACHE_KEY_REALTIME, USER_ID), JSON.stringify({
      total_value: 999,
      stocks: [{ ticker: 'NVDA', daily_change_pct: null }],
    }))
    api.getPortfolioSummary.mockReturnValue(response({
      totalValue: 110,
      marketDataDate: '2026-07-14',
      stocks: [{ ticker: 'NVDA', dailyChangePct: 0.56, priceDate: '2026-07-14' }],
    }))

    const { result } = renderHook(() => useDashboardData())

    await waitFor(() => expect(result.current.summary?.total_value).toBe(110))
    expect(api.getPortfolioSummary).toHaveBeenCalledTimes(1)
    expect(result.current.priceMap.NVDA.daily_change_pct).toBe(0.56)
    expect(result.current.priceMap.NVDA.price_date).toBe('2026-07-14')
  })

  it('revalidates once when the dashboard regains focus after the cooldown', async () => {
    const now = 1_800_000_000_000
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(now)
    const { result } = renderHook(() => useDashboardData())
    await waitFor(() => expect(result.current.loading).toBe(false))
    const callsBeforeFocus = api.getPortfolioSummary.mock.calls.length

    nowSpy.mockReturnValue(now + 61_000)
    act(() => window.dispatchEvent(new Event('focus')))

    await waitFor(() => expect(api.getPortfolioSummary).toHaveBeenCalledTimes(callsBeforeFocus + 1))
    nowSpy.mockRestore()
  })
})
