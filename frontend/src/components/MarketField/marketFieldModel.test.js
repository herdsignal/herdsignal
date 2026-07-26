import { describe, expect, it } from 'vitest'
import {
  createMarketFieldDots,
  MARKET_FIELD_DOT_COUNT,
  marketFieldSpread,
} from './marketFieldModel'

describe('marketFieldModel', () => {
  it('keeps participation count fixed while Rush becomes denser', () => {
    const flee = createMarketFieldDots(8)
    const rush = createMarketFieldDots(88)

    expect(flee).toHaveLength(MARKET_FIELD_DOT_COUNT)
    expect(rush).toHaveLength(MARKET_FIELD_DOT_COUNT)
    expect(marketFieldSpread(88).x).toBeLessThan(marketFieldSpread(8).x)
    expect(marketFieldSpread(88).y).toBeLessThan(marketFieldSpread(8).y)
  })

  it('generates deterministic dots inside the visible field', () => {
    const first = createMarketFieldDots(64, MARKET_FIELD_DOT_COUNT, 'drift')
    const second = createMarketFieldDots(64, MARKET_FIELD_DOT_COUNT, 'drift')

    expect(first).toEqual(second)
    first.forEach((dot) => {
      expect(dot.x).toBeGreaterThanOrEqual(0)
      expect(dot.x).toBeLessThanOrEqual(100)
      expect(dot.y).toBeGreaterThanOrEqual(0)
      expect(dot.y).toBeLessThanOrEqual(100)
      expect(dot.duration).toBeGreaterThan(0)
      expect(Number.isFinite(dot.shiftAX)).toBe(true)
      expect(Number.isFinite(dot.shiftAY)).toBe(true)
    })
  })

  it('moves Flee outward while Drift contracts toward the center', () => {
    const flee = createMarketFieldDots(8, MARKET_FIELD_DOT_COUNT, 'flee')
    const drift = createMarketFieldDots(68, MARKET_FIELD_DOT_COUNT, 'drift')

    const radialMotion = (dot) => {
      const centerX = dot.x - 50
      const centerY = dot.y - 50
      return centerX * dot.shiftAX + centerY * dot.shiftAY
    }

    expect(flee.filter((dot) => radialMotion(dot) > 0).length)
      .toBeGreaterThan(MARKET_FIELD_DOT_COUNT * 0.8)
    expect(drift.filter((dot) => radialMotion(dot) < 0).length)
      .toBeGreaterThan(MARKET_FIELD_DOT_COUNT * 0.8)
  })

  it('turns four-week movement into a visible horizontal flow', () => {
    const gathering = createMarketFieldDots(64, 16, 'drift', 10)
    const releasing = createMarketFieldDots(64, 16, 'drift', -10)
    const meanShift = (dots) => (
      dots.reduce((sum, dot) => sum + dot.shiftAX, 0) / dots.length
    )

    expect(meanShift(gathering)).toBeGreaterThan(meanShift(releasing))
    expect(gathering[0].duration).toBeLessThan(
      createMarketFieldDots(64, 16, 'drift', 0)[0].duration,
    )
  })

  it('keeps Calm visibly in motion on a large market field', () => {
    const calm = createMarketFieldDots(51, MARKET_FIELD_DOT_COUNT, 'calm')
    const displacement = calm.map((dot) => Math.hypot(dot.shiftAX, dot.shiftAY))
    const average = displacement.reduce((sum, value) => sum + value, 0) / displacement.length

    expect(average).toBeGreaterThan(12)
    expect(Math.max(...calm.map((dot) => dot.duration))).toBeLessThan(7.3)
  })
})
