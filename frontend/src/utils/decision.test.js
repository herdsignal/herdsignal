import { describe, expect, it } from 'vitest'
import { buildDecision } from './decision'

describe('buildDecision operational boundary', () => {
  it('keeps an unapproved research signal as HOLD', () => {
    const decision = buildDecision({
      herdData: { ticker: 'NVDA', signal: 'SELL', actionRatio: 0, herdScore: 85 },
      holding: null,
      summary: null,
    })

    expect(decision.signal).toBe('HOLD')
    expect(decision.title).toBe('보유 유지')
  })
})
