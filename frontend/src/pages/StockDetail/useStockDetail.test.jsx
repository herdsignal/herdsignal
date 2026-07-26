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

  it('loads one fixed timeline and only slices it when the chart period changes', async () => {
    const points = Array.from({ length: 20 }, (_, index) => ({
      observationDate: `2026-${String(Math.floor(index / 4) + 1).padStart(2, '0')}-${String((index % 4) * 7 + 1).padStart(2, '0')}`,
      stateScore: 40 + index,
      stage: index < 10 ? 'CALM' : 'DRIFT',
      transition: 'NEUTRAL',
      transitionEvent: false,
    }))
    api.getHerdObservationHistory.mockReturnValue(response({ points }))

    const { result } = renderHook(() => useStockDetail('nvda'))
    await waitFor(() => expect(result.current.historyLoading).toBe(false))

    expect(api.getHerdObservationHistory).toHaveBeenCalledTimes(1)
    expect(api.getHerdObservationHistory).toHaveBeenCalledWith('NVDA', 260)
    expect(result.current.historyPoints).toHaveLength(20)

    act(() => result.current.setHistoryPeriod('1m'))
    expect(result.current.historyPoints).toHaveLength(6)
    expect(api.getHerdObservationHistory).toHaveBeenCalledTimes(1)
  })

  it('stores the observed stage duration with a journal entry', async () => {
    api.getHerdObservationHistory.mockReturnValue(response({ points: [
      {
        observationDate: '2026-07-10',
        stateScore: 48,
        stage: 'CALM',
        transition: 'NEUTRAL',
        transitionEvent: false,
      },
      {
        observationDate: '2026-07-17',
        stateScore: 49,
        stage: 'CALM',
        transition: 'NEUTRAL',
        transitionEvent: false,
      },
      {
        observationDate: '2026-07-24',
        stateScore: 50,
        stage: 'CALM',
        transition: 'NEUTRAL',
        transitionEvent: false,
      },
    ] }))
    api.createSignalJournal.mockImplementation((entry) => response({
      id: 1,
      ...entry,
    }))

    const { result } = renderHook(() => useStockDetail('nvda'))
    await waitFor(() => expect(result.current.historyLoading).toBe(false))
    await act(async () => {
      await result.current.handleJournalAction('HOLD', { memo: '관찰' })
    })

    expect(api.createSignalJournal).toHaveBeenCalledWith(expect.objectContaining({
      stageDurationDays: 14,
      actionRatio: 0,
    }))
  })
})
