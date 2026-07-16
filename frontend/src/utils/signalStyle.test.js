import { describe, expect, it } from 'vitest'
import { signalStyle, signalTone } from './signalStyle'

describe('signalStyle', () => {
  it('행동별 공통 의미 색상을 반환한다', () => {
    expect(signalStyle('BUY').color).toBe('var(--action-buy)')
    expect(signalStyle('HOLD').color).toBe('var(--action-hold)')
    expect(signalStyle('SELL').color).toBe('var(--action-sell)')
  })

  it('알 수 없는 행동은 유지 상태로 처리한다', () => {
    expect(signalStyle('UNKNOWN')).toEqual(signalStyle('HOLD'))
  })

  it('판단 흐름용 색상 톤을 단순화한다', () => {
    expect(signalTone('ADD')).toBe('buy')
    expect(signalTone('HOLD')).toBe('hold')
    expect(signalTone('REDUCE')).toBe('reduce')
  })
})
