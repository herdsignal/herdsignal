import { clampHerdScore } from '../HerdLens/herdLensModel'

export const MARKET_FIELD_DOT_COUNT = 64

const MOTION_PROFILES = {
  flee: { radial: 30, tangent: 12, duration: 3.6 },
  scatter: { radial: 14, tangent: 22, duration: 4.1 },
  calm: { radial: 9, tangent: 18, duration: 4.8 },
  drift: { radial: -16, tangent: 15, duration: 4.2 },
  rush: { radial: -10, tangent: 11, duration: 3.2 },
}

export function marketFieldSpread(score) {
  const normalized = clampHerdScore(score)
  if (normalized == null) return { x: 82, y: 72 }
  return {
    x: Math.max(24, 86 - normalized * 0.62),
    y: Math.max(28, 74 - normalized * 0.46),
  }
}

export function createMarketFieldDots(
  score,
  count = MARKET_FIELD_DOT_COUNT,
  stage = 'calm',
  momentum = 0,
) {
  const dotCount = Math.max(8, Math.round(count))
  const normalized = clampHerdScore(score) ?? 50
  const spread = marketFieldSpread(normalized)
  const anchorX = 47 + normalized * 0.06
  const profile = MOTION_PROFILES[String(stage).toLowerCase()]
    ?? MOTION_PROFILES.calm
  const direction = Math.max(-20, Math.min(20, Number(momentum) || 0)) / 20

  return Array.from({ length: dotCount }, (_, index) => {
    const ratio = Math.sqrt((index + 0.5) / dotCount)
    const angle = index * 2.399963229728653
    const radialX = Math.cos(angle)
    const radialY = Math.sin(angle)
    const tangentX = -radialY
    const tangentY = radialX
    const amplitude = 0.72 + seededUnit(index, normalized, 1) * 0.56
    const tangentDirection = seededUnit(index, normalized, 2) > 0.5 ? 1 : -1
    const secondaryDirection = seededUnit(index, normalized, 3) > 0.5 ? 1 : -1
    const radialMotion = profile.radial * amplitude
    const tangentMotion = profile.tangent * tangentDirection

    return {
      x: anchorX + Math.cos(angle) * spread.x * 0.5 * ratio,
      y: 50 + Math.sin(angle) * spread.y * 0.5 * ratio,
      size: 2.5 + (index % 7 === 0 ? 2.5 : index % 3 === 0 ? 1.2 : 0),
      opacity: 0.34 + (index % 5) * 0.115,
      shiftAX: radialX * radialMotion
        + tangentX * tangentMotion
        + direction * (4 + ratio * 8),
      shiftAY: radialY * radialMotion + tangentY * tangentMotion,
      shiftBX: tangentX * profile.tangent * 0.7 * secondaryDirection,
      shiftBY: tangentY * profile.tangent * 0.7 * secondaryDirection,
      duration: profile.duration
        + seededUnit(index, normalized, 4) * 2.4
        - Math.abs(direction) * 0.7,
      delay: -seededUnit(index, normalized, 5) * (profile.duration + 2.4),
    }
  })
}

function seededUnit(index, score, salt) {
  const value = Math.sin(
    (index + 1) * 12.9898
      + (score + 1) * 0.731
      + salt * 37.719,
  ) * 43758.5453
  return value - Math.floor(value)
}
