import { stageColor, stageFromScore } from '../../utils/herdStage'

export const WATCHLIST_SORTS = [
  { value: 'recent', label: '최근 관찰' },
  { value: 'high', label: 'HERD 높은순' },
  { value: 'low', label: 'HERD 낮은순' },
]

const STAGES = ['Flee', 'Scatter', 'Calm', 'Drift', 'Rush']

function scoreOf(item) {
  const rawScore = item?.herdScore
  if (rawScore == null || rawScore === '') return null
  const score = Number(rawScore)
  return Number.isFinite(score) ? score : null
}

export function sortWatchlistObservations(items, sortBy = 'recent') {
  return [...items].sort((left, right) => {
    const leftScore = scoreOf(left)
    const rightScore = scoreOf(right)
    if (sortBy === 'high' || sortBy === 'low') {
      if (leftScore == null && rightScore == null) return left.ticker.localeCompare(right.ticker)
      if (leftScore == null) return 1
      if (rightScore == null) return -1
      return sortBy === 'high'
        ? rightScore - leftScore
        : leftScore - rightScore
    }
    const leftDate = left.lastObservedSession ?? left.scoreDate ?? ''
    const rightDate = right.lastObservedSession ?? right.scoreDate ?? ''
    return rightDate.localeCompare(leftDate) || left.ticker.localeCompare(right.ticker)
  })
}

export function summarizeWatchlistStages(items) {
  const counts = Object.fromEntries(STAGES.map((stage) => [stage, 0]))
  items.forEach((item) => {
    const score = scoreOf(item)
    const normalized = score == null ? null : stageFromScore(score)
    const stage = normalized
      ? normalized[0].toUpperCase() + normalized.slice(1)
      : null
    if (stage && stage in counts) counts[stage] += 1
  })
  return STAGES.map((stage) => ({
    stage,
    count: counts[stage],
    color: stageColor(stage),
  }))
}
