import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useStockDetail } from './useStockDetail'
import * as api from '../../api/herdApi'

vi.mock('../../api/herdApi', () => ({
  getStockHerd: vi.fn(),
  addToPortfolio: vi.fn(),
  addToWatchlist: vi.fn(),
  getStockFinancials: vi.fn(),
  getStockHerdHistory: vi.fn(),
  getStockHerdReliability: vi.fn(),
  getPortfolio: vi.fn(),
  getPortfolioSummary: vi.fn(),
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

beforeEach(() => {
  api.getPortfolio.mockReturnValue(response([]))
  api.getPortfolioSummary.mockReturnValue(response(null))
  api.getSignalJournal.mockReturnValue(response([]))
  api.getStockHerdHistory.mockReturnValue(response({ points: [] }))
  api.getStockHerdReliability.mockReturnValue(response(null))
  api.getStockFinancials.mockReturnValue(response(null))
})

describe('useStockDetail', () => {
  it('ignores a slower response from the previous ticker', async () => {
    const aapl = deferred()
    const nvda = deferred()
    api.getStockHerd
      .mockReturnValueOnce(aapl.promise)
      .mockReturnValueOnce(nvda.promise)

    const { result, rerender } = renderHook(
      ({ ticker }) => useStockDetail(ticker),
      { initialProps: { ticker: 'aapl' } },
    )

    rerender({ ticker: 'nvda' })
    await act(async () => {
      nvda.resolve({ data: { data: { ticker: 'NVDA', herdScore: 60 } } })
    })
    await waitFor(() => expect(result.current.herdData?.ticker).toBe('NVDA'))

    await act(async () => {
      aapl.resolve({ data: { data: { ticker: 'AAPL', herdScore: 20 } } })
    })
    expect(result.current.herdData?.ticker).toBe('NVDA')
  })

  it('resets action status when the ticker changes', async () => {
    api.getStockHerd.mockImplementation((ticker) => response({ ticker, herdScore: 50 }))
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
