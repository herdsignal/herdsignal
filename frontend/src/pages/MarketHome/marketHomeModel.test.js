import { describe, expect, it } from 'vitest'
import { marketHomeViewModel } from './marketHomeModel'

describe('marketHomeViewModel', () => {
  it('accepts only the S&P 500 aggregate scope', () => {
    const aggregate = marketHomeViewModel({
      observation: {
        availabilityStatus: 'AVAILABLE',
        scope: 'MARKET_AGGREGATE',
        stateScore: 64,
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
    expect(equity.score).toBeNull()
    expect(equity.unavailable).toBe(true)
  })
})

