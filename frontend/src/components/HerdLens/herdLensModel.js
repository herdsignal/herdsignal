import {
  normalizeStage,
  stageDescription,
  stageFromScore,
  stageLabelFromScore,
} from '../../utils/herdStage'

export const DEFAULT_LENS_DOT_COUNT = 12

const DOT_ROWS = [35, 64, 43, 58, 31, 68, 47, 56, 34, 65, 44, 54]

export function clampHerdScore(value) {
  if (value == null || value === '') return null
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return null
  return Math.max(0, Math.min(100, numeric))
}

export function herdLensSpread(score) {
  const normalized = clampHerdScore(score)
  if (normalized == null) return 82
  return Math.max(28, Math.min(82, 88 - normalized * 0.68))
}

export function createHerdLensDots(score, dotCount = DEFAULT_LENS_DOT_COUNT) {
  const count = Math.max(2, Math.round(dotCount))
  const spread = herdLensSpread(score)

  return Array.from({ length: count }, (_, index) => {
    const position = count === 1 ? 0 : index / (count - 1) - 0.5
    return {
      x: 50 + position * spread,
      y: DOT_ROWS[index % DOT_ROWS.length],
      size: index % 5 === 0 ? 4 : 3,
      opacity: 0.42 + (index % 4) * 0.13,
    }
  })
}

export function resolvePreviousScore(score, previousScore, delta) {
  const normalized = clampHerdScore(score)
  if (normalized == null) return null

  const explicit = clampHerdScore(previousScore)
  if (explicit != null) return explicit

  const numericDelta = Number(delta)
  if (!Number.isFinite(numericDelta)) return null
  return clampHerdScore(normalized - numericDelta)
}

export function herdLensLabel({ score, stage, previousScore }) {
  const normalized = clampHerdScore(score)
  if (normalized == null) return 'HERD 관찰값 없음'

  const normalizedStage = normalizeStage(stage) || stageFromScore(normalized)
  const stageLabel = normalizedStage
    ? stageLabelFromScore(normalized)
    : '상태 미확인'
  const description = normalizedStage ? stageDescription(normalizedStage) : ''
  const previous = clampHerdScore(previousScore)
  const movement = previous == null
    ? ''
    : `, 4주 전 ${Math.round(previous)}에서 ${Math.round(normalized - previous)} 변화`

  return `HERD ${Math.round(normalized)}, ${stageLabel}, ${description}${movement}`
}
