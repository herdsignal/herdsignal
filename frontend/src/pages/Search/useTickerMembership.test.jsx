import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  addToPortfolio,
  addToWatchlist,
  getPortfolio,
  getWatchlist,
} from '../../api/herdApi'
import { userCacheKey, CACHE_KEY_REALTIME } from '../../features/portfolio/portfolioCache'
import { useTickerMembership } from './useTickerMembership'

vi.mock('../../api/herdApi', () => ({
  addToPortfolio: vi.fn(),
  addToWatchlist: vi.fn(),
  getPortfolio: vi.fn(),
  getWatchlist: vi.fn(),
}))

beforeEach(() => {
  localStorage.clear()
  getPortfolio.mockResolvedValue({ data: { data: [{ ticker: 'AAPL' }] } })
  getWatchlist.mockResolvedValue({ data: { data: [{ ticker: 'MSFT' }] } })
  addToPortfolio.mockResolvedValue({})
  addToWatchlist.mockResolvedValue({})
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('useTickerMembership', () => {
  it('does not read or mutate private membership when disabled', async () => {
    const { result } = renderHook(() => useTickerMembership({
      selectedTicker: 'NVDA',
      userId: null,
      enabled: false,
    }))

    await act(async () => {
      await result.current.handleAddPortfolio('NVDA')
      await result.current.handleAddWatchlist('NVDA')
    })

    expect(getPortfolio).not.toHaveBeenCalled()
    expect(getWatchlist).not.toHaveBeenCalled()
    expect(addToPortfolio).not.toHaveBeenCalled()
    expect(addToWatchlist).not.toHaveBeenCalled()
  })

  it('marks existing membership and clears portfolio cache after a new addition', async () => {
    const onAdded = vi.fn()
    const { result, rerender } = renderHook(
      ({ ticker }) => useTickerMembership({
        selectedTicker: ticker,
        userId: 'user-1',
        onPortfolioAdded: onAdded,
      }),
      { initialProps: { ticker: 'AAPL' } }
    )

    await waitFor(() => expect(result.current.portfolioStatus).toBe('exists'))
    rerender({ ticker: 'NVDA' })
    await waitFor(() => expect(result.current.portfolioStatus).toBe('idle'))
    localStorage.setItem(userCacheKey(CACHE_KEY_REALTIME, 'user-1'), '{}')

    await act(async () => result.current.handleAddPortfolio('NVDA'))

    expect(addToPortfolio).toHaveBeenCalledWith('NVDA')
    expect(onAdded).toHaveBeenCalledWith('NVDA')
    expect(localStorage.getItem(userCacheKey(CACHE_KEY_REALTIME, 'user-1'))).toBeNull()
  })
})
