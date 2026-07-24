import { describe, expect, it } from 'vitest'
import {
  evaluateFundamentalGuard,
  fmtCurrencyCompact,
  fmtNumber,
} from './stockFundamentalModel'

describe('stock detail domain models', () => {
  it('keeps missing financial values explicit', () => {
    expect(fmtCurrencyCompact(null)).toBe('—')
    expect(fmtNumber(undefined)).toBe('—')
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
