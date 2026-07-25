import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useMarketHomeData } from './useMarketHomeData'
import * as api from '../../api/herdApi'
import * as cache from '../../features/market/marketCache'

vi.mock('../../api/herdApi', () => ({
  getDataStatus: vi.fn(),
  getHerdObservation: vi.fn(),
}))

vi.mock('../../features/market/marketCache', () => ({
  readMarketObservationCache: vi.fn(),
  writeMarketObservationCache: vi.fn(),
}))

beforeEach(() => {
  cache.readMarketObservationCache.mockReturnValue({
    availabilityStatus: 'AVAILABLE',
    scope: 'MARKET_AGGREGATE',
    stateScore: 55,
  })
  api.getHerdObservation.mockResolvedValue({
    data: { data: {
      availabilityStatus: 'AVAILABLE',
      scope: 'MARKET_AGGREGATE',
      stateScore: 64,
    } },
  })
  api.getDataStatus.mockResolvedValue({
    data: { data: { status: 'FRESH' } },
  })
})

describe('useMarketHomeData', () => {
  it('shows the cached observation first and replaces it with the latest S1 value', async () => {
    const { result } = renderHook(() => useMarketHomeData())

    expect(result.current.observation.stateScore).toBe(55)
    await waitFor(() => {
      expect(result.current.observation.stateScore).toBe(64)
    })
    expect(cache.writeMarketObservationCache).toHaveBeenCalledWith(
      expect.objectContaining({ stateScore: 64 }),
    )
    expect(result.current.dataStatus.status).toBe('FRESH')
  })
})
