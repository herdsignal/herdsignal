import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePortfolioData } from './usePortfolioData'
import * as api from '../../api/herdApi'
import {
  CACHE_KEY_REALTIME,
  CACHE_KEY_VERSION,
  PORTFOLIO_CACHE_VERSION,
  userCacheKey,
} from './portfolioDataModel'

vi.mock('../../api/herdApi', () => ({
  getCashBalance: vi.fn(),
  getPortfolio: vi.fn(),
  getHerdObservations: vi.fn(),
  getPortfolioRealtime: vi.fn(),
  getPortfolioSummary: vi.fn(),
}))

function response(data) {
  return Promise.resolve({ data: { data } })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  api.getPortfolio.mockReturnValue(response([{ ticker: 'AAPL' }]))
  api.getPortfolioSummary.mockReturnValue(response({
    totalValue: 110,
    stocks: [{ ticker: 'AAPL', dailyChangePct: 0.56 }],
  }))
  api.getHerdObservations.mockReturnValue(response({
    observations: [{
      ticker: 'AAPL',
      availabilityStatus: 'AVAILABLE',
      stateScore: 40,
      stage: 'CALM',
    }],
  }))
  api.getCashBalance.mockReturnValue(response({ cashAmount: 10 }))
})

afterEach(() => cleanup())

describe('usePortfolioData', () => {
  it('revalidates the summary and loads State S1 observations', async () => {
    const setTargetWeights = vi.fn()
    localStorage.setItem(CACHE_KEY_VERSION, PORTFOLIO_CACHE_VERSION)
    localStorage.setItem(
      userCacheKey(CACHE_KEY_REALTIME, 'user-1'),
      JSON.stringify({ total_value: 999 }),
    )

    const { result } = renderHook(() => usePortfolioData({
      userId: 'user-1',
      setTargetWeights,
    }))

    await waitFor(() => expect(result.current.loading).toBe(false))
    await waitFor(() => expect(result.current.summary?.total_asset_value).toBe(120))
    expect(api.getPortfolioSummary).toHaveBeenCalledTimes(1)
    expect(api.getHerdObservations).toHaveBeenCalledTimes(1)
    expect(result.current.herdMap.AAPL?.herdScore).toBe(40)
  })

  it('revalidates once when the page regains focus after the cooldown', async () => {
    const now = 1_800_000_000_000
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(now)
    const setTargetWeights = vi.fn()
    const { result } = renderHook(() => usePortfolioData({
      userId: 'user-1',
      setTargetWeights,
    }))
    await waitFor(() => expect(result.current.loading).toBe(false))
    const callsBeforeFocus = api.getPortfolioSummary.mock.calls.length

    nowSpy.mockReturnValue(now + 61_000)
    act(() => window.dispatchEvent(new Event('focus')))

    await waitFor(() => {
      expect(api.getPortfolioSummary).toHaveBeenCalledTimes(callsBeforeFocus + 1)
    })
    nowSpy.mockRestore()
  })
})
