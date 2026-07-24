import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getHerdObservation, searchStocks } from '../../api/herdApi'
import { useStockSearch } from './useStockSearch'

vi.mock('../../api/herdApi', () => ({
  getHerdObservation: vi.fn(),
  searchStocks: vi.fn(),
}))

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  searchStocks.mockResolvedValue({ data: { data: { results: [] } } })
  getHerdObservation.mockResolvedValue({
    data: { data: {
      ticker: 'NVDA',
      availabilityStatus: 'AVAILABLE',
      stateScore: 50,
      stage: 'CALM',
    } },
  })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('useStockSearch', () => {
  it('does not search whitespace or a one-character query', () => {
    const { result, rerender } = renderHook(
      ({ query }) => useStockSearch(query),
      { initialProps: { query: '  ' } }
    )
    rerender({ query: 'A' })
    act(() => vi.advanceTimersByTime(300))

    expect(result.current.searchResult).toBeNull()
    expect(searchStocks).not.toHaveBeenCalled()
  })

  it('combines symbol discovery with the latest HERD snapshot', async () => {
    const { result } = renderHook(() => useStockSearch('NVDA'))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300)
    })

    expect(result.current.searchResult?.status).toBe('found')
    expect(searchStocks).toHaveBeenCalledWith('NVDA')
    expect(getHerdObservation).toHaveBeenCalledWith('NVDA')
    expect(result.current.recentSearches[0]).toBe('NVDA')
  })
})
