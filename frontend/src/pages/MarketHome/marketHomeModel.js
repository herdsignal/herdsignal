import {
  observationFreshnessLabel,
  observationScore,
  observationStage,
} from '../../utils/herdObservation'

export function marketHomeViewModel({
  observation,
  loading,
  observationError,
}) {
  const score = observationScore(observation)
  const stage = observationStage(observation)
  const scopeValid = observation?.scope === 'MARKET_AGGREGATE'

  return {
    score: scopeValid ? score : null,
    stage: scopeValid ? stage : null,
    scopeValid,
    loading: loading && observation == null,
    unavailable: !loading && (!scopeValid || score == null),
    observationDate: observation?.lastObservedSession
      ?? observation?.observationDate
      ?? null,
    freshness: observationFreshnessLabel(observation),
    observationError,
  }
}

export function formatMarketDate(value) {
  if (!value) return '기준일 없음'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
