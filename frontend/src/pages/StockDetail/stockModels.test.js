import { describe, expect, it } from 'vitest'
import {
  evaluateFundamentalGuard,
  fmtCurrencyCompact,
  fmtNumber,
} from './stockFundamentalModel'
import {
  currentSignalReliability,
  fmtReliabilityPct,
} from './stockReliabilityModel'

describe('stock detail domain models', () => {
  it('keeps missing financial and reliability values explicit', () => {
    expect(fmtCurrencyCompact(null)).toBe('—')
    expect(fmtNumber(undefined)).toBe('—')
    expect(fmtReliabilityPct(null)).toBe('—')
  })

  it('does not present an operational trade edge while the action is HOLD', () => {
    const current = currentSignalReliability(
      { signal: 'HOLD' },
      { fitScore: 61, totalSignalSamples: 20, sampleQuality: 'MEDIUM' }
    )
    expect(current.label).toBe('종목별 모델 적합도')
    expect(current.caption).toContain('표본 품질')
  })

  it('separates financial deterioration from the HERD state', () => {
    const guard = evaluateFundamentalGuard({
      eps: -1,
      trailingPe: null,
      operatingMargin: -5,
      totalRevenue: 100,
      marketCap: 1_000,
    }, { signal: 'HOLD' })

    expect(guard.level).toBe('RISK')
    expect(guard.reasons).toContain('적자와 영업손실 동시 확인')
  })
})
