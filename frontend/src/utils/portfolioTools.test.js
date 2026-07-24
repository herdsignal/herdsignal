import { describe, expect, it } from 'vitest'
import { operationalSignal, opportunityRows, portfolioRows } from './portfolioTools'

describe('portfolioTools operational boundary', () => {
  it('does not promote a research signal when the operational ratio is zero', () => {
    expect(operationalSignal({ signal: 'BUY', actionRatio: 0 })).toBe('HOLD')

    const [row] = opportunityRows([{ ticker: 'NVDA', signal: 'BUY', actionRatio: 0, herdV4: 12 }])
    expect(row.signal).toBe('HOLD')
    expect(row.stateSignal).toBe('BUY')
    expect(row.queueState).toBe('WAIT')
    expect(row.reason).toBe('BUY 연구 상태')
  })

  it('prefers the explicit API action boundary over legacy fields', () => {
    const item = {
      signal: 'HOLD',
      legacySignal: 'BUY',
      operationalAction: 'HOLD',
      actionAuthorized: false,
      actionRatio: 0.25,
    }
    expect(operationalSignal(item)).toBe('HOLD')
    expect(opportunityRows([item])[0].stateSignal).toBe('BUY')
  })

  it('requires explicit authorization and a positive operational ratio', () => {
    expect(operationalSignal({
      signal: 'ADD',
      operationalAction: 'ADD',
      operationalActionRatio: 0.05,
      actionAuthorized: true,
    })).toBe('ADD')
    expect(operationalSignal({
      signal: 'ADD',
      operationalAction: 'ADD',
      actionRatio: 0.05,
    })).toBe('HOLD')
  })

  it('fails closed for stale cache values and invalid action codes', () => {
    expect(operationalSignal({
      operationalAction: 'SELL',
      actionRatio: 0.15,
    })).toBe('HOLD')
    expect(operationalSignal({
      operationalAction: 'STRONG_BUY',
      operationalActionRatio: 0.15,
      actionAuthorized: true,
    })).toBe('HOLD')
  })

  it('keeps portfolio rebalance math independent from an unapproved action signal', () => {
    const [row] = portfolioRows(
      [{ ticker: 'NVDA' }],
      { total_value: 100, stocks: [{ ticker: 'NVDA', market_value: 100 }] },
      { NVDA: { signal: 'SELL', actionRatio: 0 } },
      { NVDA: '50' },
    )

    expect(row.signal).toBe('HOLD')
    expect(row.stateSignal).toBe('SELL')
    expect(row.action).toBe('추가매수 금지')
  })
})
