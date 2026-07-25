import { describe, expect, it } from 'vitest'
import {
  clampHerdScore,
  createHerdLensDots,
  herdLensLabel,
  herdLensSpread,
  resolvePreviousScore,
} from './herdLensModel'

describe('herdLensModel', () => {
  it('uses the same number of dots while density increases with HERD', () => {
    const flee = createHerdLensDots(10)
    const rush = createHerdLensDots(90)

    expect(flee).toHaveLength(12)
    expect(rush).toHaveLength(12)
    expect(herdLensSpread(90)).toBeLessThan(herdLensSpread(10))
    expect(rush.at(-1).x - rush[0].x).toBeLessThan(
      flee.at(-1).x - flee[0].x,
    )
  })

  it('clamps current and derived previous scores to the visible range', () => {
    expect(clampHerdScore(-20)).toBe(0)
    expect(clampHerdScore(130)).toBe(100)
    expect(clampHerdScore('unknown')).toBeNull()
    expect(resolvePreviousScore(8, null, 15)).toBe(0)
    expect(resolvePreviousScore(92, 120, null)).toBe(100)
  })

  it('describes state and movement without turning it into an action', () => {
    const label = herdLensLabel({
      score: 83,
      stage: 'rush',
      previousScore: 74,
    })

    expect(label).toContain('HERD 83')
    expect(label).toContain('Rush')
    expect(label).toContain('4주 전 74')
    expect(label).not.toMatch(/매수|매도|익절/)
  })
})

