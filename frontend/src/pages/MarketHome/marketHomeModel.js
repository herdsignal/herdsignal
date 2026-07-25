import {
  observationFreshnessLabel,
  observationScore,
  observationStage,
} from '../../utils/herdObservation'

export function marketHomeViewModel({
  observation,
  dataStatus,
  loading,
  observationError,
  statusError,
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
    systemStatus: statusError
      ? '상태 확인 불가'
      : dataStatus?.status === 'FRESH'
        ? '수집 정상'
        : dataStatus?.status === 'RUNNING'
          ? '업데이트 중'
          : dataStatus?.status
            ? '수집 확인 필요'
            : null,
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

