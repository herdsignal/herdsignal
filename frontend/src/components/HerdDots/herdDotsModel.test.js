import { describe, expect, it } from 'vitest'
import {
  advanceHerdDot,
  createHerdDots,
  herdDotColor,
  herdFlowProfile,
  randomHerdTarget,
} from './herdDotsModel'

const midpointRandom = () => 0.5

describe('herdDotsModel', () => {
  it('maps the five HERD states to stable colors and density profiles', () => {
    expect(herdDotColor(10)).toBe('#3B82F6')
    expect(herdDotColor(30)).toBe('#60A5FA')
    expect(herdDotColor(50)).toBe('#A3AAB8')
    expect(herdDotColor(65)).toBe('#F97316')
    expect(herdDotColor(80)).toBe('#EF4444')
    expect(herdFlowProfile(80).spreadX).toBeLessThan(herdFlowProfile(10).spreadX)
  })

  it('keeps generated targets inside the visible field', () => {
    for (const score of [10, 30, 50, 65, 80]) {
      const target = randomHerdTarget(herdFlowProfile(score), midpointRandom)
      expect(target.tx).toBeGreaterThanOrEqual(0.04)
      expect(target.tx).toBeLessThanOrEqual(0.96)
      expect(target.ty).toBeGreaterThanOrEqual(0.08)
      expect(target.ty).toBeLessThanOrEqual(0.92)
    }
  })

  it('respects the active ratio and velocity cap', () => {
    const profile = herdFlowProfile(80)
    const dots = createHerdDots({
      dotCount: 10,
      profile,
      score: 80,
      dpr: 1,
      activeRatio: 0.3,
      random: midpointRandom,
    })
    expect(dots.filter((dot) => dot.active)).toHaveLength(3)
    dots[0].vx = 1
    dots[0].vy = 1
    advanceHerdDot(dots[0], {
      profile,
      tick: 1,
      enhanced: false,
      direction: 0,
      random: midpointRandom,
    })
    expect(Math.hypot(dots[0].vx, dots[0].vy)).toBeLessThanOrEqual(profile.maxV + 1e-10)
  })
})
