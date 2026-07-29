import { describe, expect, it } from 'vitest'
import { formatMarketDelta, marketHomeViewModel } from './marketHomeModel'

describe('marketHomeViewModel', () => {
  it('accepts only the S&P 500 aggregate scope', () => {
    const aggregate = marketHomeViewModel({
      observation: {
        availabilityStatus: 'AVAILABLE',
        scope: 'MARKET_AGGREGATE',
        stateScore: 64,
        delta4w: 3.25,
      },
      loading: false,
    })
    const equity = marketHomeViewModel({
      observation: {
        availabilityStatus: 'AVAILABLE',
        scope: 'EQUITY',
        stateScore: 64,
      },
      loading: false,
    })

    expect(aggregate.score).toBe(64)
    expect(aggregate.delta4w).toBe(3.25)
    expect(equity.score).toBeNull()
    expect(equity.unavailable).toBe(true)
  })

  it('formats four-week movement without recommendation language', () => {
    expect(formatMarketDelta(3.25)).toBe('4W +3.3')
    expect(formatMarketDelta(-2)).toBe('4W -2.0')
    expect(formatMarketDelta(null)).toBe('4W —')
  })

  it('shows daily nowcast while preserving the weekly confirmed reading', () => {
    const view = marketHomeViewModel({
      observation: {
        availabilityStatus: 'AVAILABLE',
        scope: 'MARKET_AGGREGATE',
        stateScore: 52,
        lastObservedSession: '2026-07-24',
      },
      dailyObservation: {
        availabilityStatus: 'AVAILABLE',
        scope: 'MARKET_AGGREGATE',
        stateScore: 57,
        lastObservedSession: '2026-07-28',
        delta4w: 2.5,
      },
      loading: false,
    })

    expect(view.score).toBe(57)
    expect(view.provisional).toBe(true)
    expect(view.freshness).toBe('일간 잠정 관찰')
    expect(view.confirmedScore).toBe(52)
    expect(view.confirmedDate).toBe('2026-07-24')
  })
})
