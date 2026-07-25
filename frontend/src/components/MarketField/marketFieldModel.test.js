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
    const first = createMarketFieldDots(64)
    const second = createMarketFieldDots(64)

    expect(first).toEqual(second)
    first.forEach((dot) => {
      expect(dot.x).toBeGreaterThanOrEqual(0)
      expect(dot.x).toBeLessThanOrEqual(100)
      expect(dot.y).toBeGreaterThanOrEqual(0)
      expect(dot.y).toBeLessThanOrEqual(100)
    })
  })
})

