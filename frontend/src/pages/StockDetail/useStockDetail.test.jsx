import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useStockDetail } from './useStockDetail'
import * as api from '../../api/herdApi'

vi.mock('../../api/herdApi', () => ({
  getHerdObservation: vi.fn(),
  getHerdObservationHistory: vi.fn(),
  addToPortfolio: vi.fn(),
  addToWatchlist: vi.fn(),
  getStockFinancials: vi.fn(),
  getSignalJournal: vi.fn(),
  createSignalJournal: vi.fn(),
  deleteSignalJournal: vi.fn(),
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { authenticated: true, id: 'user-1' } }),
}))

function response(data) {
  return Promise.resolve({ data: { data } })
}

function deferred() {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}

function observation(ticker, score = 50) {
  return {
    ticker,
    availabilityStatus: 'AVAILABLE',
    freshnessStatus: 'FRESH',
    stateScore: score,
    stage: 'CALM',
    observationDate: '2026-07-24',
    lastObservedSession: '2026-07-24',
    transition: 'NEUTRAL',
    families: {
      priceExtension: score,
      trendPosition: score,
      relativePosition: score,
      participation: score,
    },
    downsideRiskContext: 50,
  }
}

beforeEach(() => {
  api.getSignalJournal.mockReturnValue(response([]))
  api.getHerdObservation.mockImplementation((ticker) =>
    response(observation(ticker)))
  api.getHerdObservationHistory.mockReturnValue(response({ points: [] }))
  api.getStockFinancials.mockReturnValue(response(null))
})

describe('useStockDetail', () => {
  it('ignores a slower response from the previous ticker', async () => {
    const aapl = deferred()
    const nvda = deferred()
    api.getHerdObservation
      .mockReturnValueOnce(aapl.promise)
      .mockReturnValueOnce(nvda.promise)

    const { result, rerender } = renderHook(
      ({ ticker }) => useStockDetail(ticker),
      { initialProps: { ticker: 'aapl' } },
    )

    rerender({ ticker: 'nvda' })
    await act(async () => {
      nvda.resolve({ data: { data: observation('NVDA', 60) } })
    })
    await waitFor(() => expect(result.current.observation?.ticker).toBe('NVDA'))
    expect(result.current.herdScore).toBe(60)

    await act(async () => {
      aapl.resolve({ data: { data: observation('AAPL', 20) } })
    })
    expect(result.current.observation?.ticker).toBe('NVDA')
  })

  it('resets action status when the ticker changes', async () => {
    api.addToPortfolio.mockResolvedValue({})

    const { result, rerender } = renderHook(
      ({ ticker }) => useStockDetail(ticker),
      { initialProps: { ticker: 'aapl' } },
    )
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => { await result.current.handleAddPortfolio() })
    expect(result.current.portfolioStatus).toBe('added')

    rerender({ ticker: 'nvda' })
    await waitFor(() => expect(result.current.portfolioStatus).toBe('idle'))
  })
})
