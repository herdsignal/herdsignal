import {
  observationFreshnessLabel,
  observationScore,
  observationStage,
} from '../../utils/herdObservation'

export function marketHomeViewModel({
  observation,
  dailyObservation,
  loading,
  observationError,
}) {
  const dailyScopeValid = dailyObservation?.scope === 'MARKET_AGGREGATE'
  const dailyScore = dailyScopeValid ? observationScore(dailyObservation) : null
  const displayed = dailyScore == null ? observation : dailyObservation
  const score = observationScore(displayed)
  const stage = observationStage(displayed)
  const scopeValid = observation?.scope === 'MARKET_AGGREGATE'

  return {
    score: scopeValid ? score : null,
    stage: scopeValid ? stage : null,
    scopeValid,
    loading: loading && observation == null,
    unavailable: !loading && (!scopeValid || score == null),
    observationDate: displayed?.lastObservedSession
      ?? displayed?.observationDate
      ?? null,
    delta4w: finiteNumber(displayed?.delta4w),
    freshness: dailyScore == null
      ? observationFreshnessLabel(observation)
      : '일간 잠정 관찰',
    provisional: dailyScore != null,
    confirmedScore: scopeValid ? observationScore(observation) : null,
    confirmedStage: scopeValid ? observationStage(observation) : null,
    confirmedDate: observation?.lastObservedSession
      ?? observation?.observationDate
      ?? null,
    observationError,
  }
}

export function formatMarketDelta(value) {
  if (value == null) return '4W —'
  const sign = value > 0 ? '+' : ''
  return `4W ${sign}${value.toFixed(1)}`
}

function finiteNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}
