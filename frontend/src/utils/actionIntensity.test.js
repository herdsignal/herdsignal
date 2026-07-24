import { describe, expect, it } from 'vitest'
import { actionBasisLabel, actionIntensity } from './actionIntensity'

describe('action intensity', () => {
  it('maps numeric ratios without changing the action boundary', () => {
    expect(actionIntensity(0).label).toBe('관찰')
    expect(actionIntensity(0.05).label).toBe('낮음')
    expect(actionIntensity(0.15).label).toBe('중간')
    expect(actionIntensity(0.16).label).toBe('높음')
  })

  it('describes direction without exposing an exact percentage', () => {
    expect(actionBasisLabel({
      operationalAction: 'ADD',
      operationalActionRatio: 0.05,
      actionAuthorized: true,
    }))
      .toBe('낮음 강도로 분할매수 검토')
    expect(actionBasisLabel({
      operationalAction: 'REDUCE',
      operationalActionRatio: 0.05,
      actionAuthorized: true,
    }))
      .toBe('낮음 강도로 비중 축소 검토')
    expect(actionBasisLabel({ signal: 'BUY', actionRatio: 0.08 }))
      .toBe('현재 비중 유지')
  })
})
