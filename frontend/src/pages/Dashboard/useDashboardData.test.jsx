import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useDashboardData } from './useDashboardData'
import * as api from '../../api/herdApi'
import {
  CACHE_KEY_REALTIME,
  CACHE_KEY_TIME,
  CACHE_KEY_VERSION,
  DASHBOARD_CACHE_VERSION,
} from './dashboardModel'

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

describe('useDashboardData cache recovery', () => {
  it('refetches both resources when only the summary cache exists', async () => {
    localStorage.setItem(CACHE_KEY_VERSION, DASHBOARD_CACHE_VERSION)
    localStorage.setItem(CACHE_KEY_REALTIME, JSON.stringify({ total_value: 999 }))
    localStorage.setItem(CACHE_KEY_TIME, new Date().toISOString())

    const { result } = renderHook(() => useDashboardData())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(api.getPortfolioSummary).toHaveBeenCalledTimes(1)
    expect(api.getPortfolioHerd).toHaveBeenCalledTimes(1)
    expect(result.current.herdMap.AAPL?.herdScore).toBe(40)
    expect(result.current).toHaveProperty('assetStartValue', 100)
  })
})
