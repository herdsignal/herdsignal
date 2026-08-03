import { describe, expect, it } from 'vitest'
import {
  integrityLabel,
  marketFacts,
  normalized,
  pricePathValue,
} from './stockOperatingReviewModel'

describe('stock operating review presentation', () => {
  it('keeps objective and personal review shapes compatible', () => {
    expect(normalized({ status: 'AVAILABLE', dataGate: { reasons: [] } }).status)
      .toBe('OBSERVE')
    expect(normalized({
      objective: { assessments: [] },
      synthesis: { decision: 'OBSERVE', limitations: ['NO_DIRECTION'] },
    }).limitations).toEqual(['NO_DIRECTION'])
  })

  it('does not hide ledger integrity failures as missing price data', () => {
    expect(pricePathValue({ status: 'BLOCKED_INTEGRITY' })).toBe('검증 차단')
    expect(integrityLabel('MISMATCH')).toBe('원장 무결성 불일치')
    expect(integrityLabel('LEGACY_UNVERIFIED')).toContain('기존 기록')
  })

  it('shows only available market facts with explicit attribution labels', () => {
    const facts = marketFacts({ evidencePacket: { facts: [
      {
        id: 'MARKET.ATTRIBUTION.CLASS', quality: 'AVAILABLE',
        label: '최근 약세 귀속', value: 'SECTOR_COMMON',
      },
      { id: 'MARKET.SPY.RETURN_63', quality: 'NO_VIEW', value: '-0.1' },
    ] } })

    expect(facts).toHaveLength(1)
    expect(facts[0].displayValue).toBe('섹터 공통')
  })
})
