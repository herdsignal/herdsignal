import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useDashboardMarketData } from './useDashboardMarketData'
import { CACHE_KEY_SPY } from './dashboardModel'
import * as api from '../../api/herdApi'

vi.mock('../../api/herdApi', () => ({
  getHerdObservation: vi.fn(),
  getHerdObservationHistory: vi.fn(),
}))

vi.mock('../../utils/currency', () => ({
  fetchExchangeRate: vi.fn().mockResolvedValue(null),
}))

beforeEach(() => {
  api.getHerdObservation.mockResolvedValue({
    data: { data: {
      ticker: 'SPY',
      availabilityStatus: 'AVAILABLE',
      stateScore: 31,
      lastObservedSession: '2026-07-10',
    } },
  })
  api.getHerdObservationHistory.mockResolvedValue({
    data: { data: { points: [] } },
  })
})

describe('shared SPY market data', () => {
  it('shows cache immediately but replaces it with the backend latest value', async () => {
    localStorage.setItem(CACHE_KEY_SPY, JSON.stringify({
      ticker: 'SPY',
      availabilityStatus: 'AVAILABLE',
      stateScore: 55,
      lastObservedSession: '2026-07-01',
    }))

    const { result } = renderHook(() => useDashboardMarketData())

    expect(result.current.spyScore).toBe(55)
    await waitFor(() => expect(result.current.spyScore).toBe(31))
    expect(api.getHerdObservation).toHaveBeenCalledWith('SPY')
  })

  it('does not substitute a v4-like neutral score when S1 is unavailable', async () => {
    api.getHerdObservation.mockResolvedValue({
      data: { data: {
        ticker: 'SPY',
        availabilityStatus: 'UNAVAILABLE',
        stateScore: null,
      } },
    })
    const { result } = renderHook(() => useDashboardMarketData())
    await waitFor(() => expect(result.current.spyData).not.toBeNull())
    expect(result.current.spyScore).toBeNull()
  })
})
