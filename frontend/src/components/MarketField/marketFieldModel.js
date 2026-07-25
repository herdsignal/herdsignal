import { clampHerdScore } from '../HerdLens/herdLensModel'

export const MARKET_FIELD_DOT_COUNT = 64

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
) {
  const dotCount = Math.max(8, Math.round(count))
  const normalized = clampHerdScore(score) ?? 50
  const spread = marketFieldSpread(normalized)
  const anchorX = 47 + normalized * 0.06

  return Array.from({ length: dotCount }, (_, index) => {
    const ratio = Math.sqrt((index + 0.5) / dotCount)
    const angle = index * 2.399963229728653
    return {
      x: anchorX + Math.cos(angle) * spread.x * 0.5 * ratio,
      y: 50 + Math.sin(angle) * spread.y * 0.5 * ratio,
      size: 2 + (index % 7 === 0 ? 2 : index % 3 === 0 ? 1 : 0),
      opacity: 0.28 + (index % 5) * 0.11,
    }
  })
}

