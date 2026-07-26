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
})
