import { describe, expect, it } from 'vitest'
import { actionBasisLabel, actionIntensity } from './actionIntensity'

describe('action intensity', () => {
  it('maps research ratios to broad user-facing levels', () => {
    expect(actionIntensity(0).label).toBe('관찰')
    expect(actionIntensity(0.05).label).toBe('낮음')
    expect(actionIntensity(0.15).label).toBe('중간')
    expect(actionIntensity(0.16).label).toBe('높음')
  })

  it('describes direction without exposing an exact percentage', () => {
    expect(actionBasisLabel({ signal: 'BUY', actionRatio: 0.08 }))
      .toBe('중간 강도로 분할매수 검토')
    expect(actionBasisLabel({ signal: 'SELL', actionRatio: 0.20 }))
      .toBe('높음 강도로 비중 축소 검토')
  })
})
