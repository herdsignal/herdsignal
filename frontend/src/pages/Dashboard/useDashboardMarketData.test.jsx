import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useDashboardMarketData } from './useDashboardMarketData'
import { CACHE_KEY_SPY } from './dashboardModel'
import * as api from '../../api/herdApi'

vi.mock('../../api/herdApi', () => ({
  getStockHerd: vi.fn(),
  getSpyHerdHistory: vi.fn(),
}))

vi.mock('../../utils/currency', () => ({
  fetchExchangeRate: vi.fn().mockResolvedValue(null),
}))

beforeEach(() => {
  api.getStockHerd.mockResolvedValue({
    data: { data: { ticker: 'SPY', herdScore: 31, scoreDate: '2026-07-10' } },
  })
  api.getSpyHerdHistory.mockResolvedValue({ data: { data: { points: [] } } })
})

describe('shared SPY market data', () => {
  it('shows cache immediately but replaces it with the backend latest value', async () => {
    localStorage.setItem(CACHE_KEY_SPY, JSON.stringify({
      ticker: 'SPY', herdScore: 55, scoreDate: '2026-07-01',
    }))

    const { result } = renderHook(() => useDashboardMarketData())

    expect(result.current.spyScore).toBe(55)
    await waitFor(() => expect(result.current.spyScore).toBe(31))
    expect(api.getStockHerd).toHaveBeenCalledWith('SPY')
  })
})
