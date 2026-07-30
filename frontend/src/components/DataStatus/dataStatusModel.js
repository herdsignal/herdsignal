const STATUS_META = {
  FRESH: { label: '데이터 최신', tone: 'fresh' },
  WARNING: { label: '일부 확인', tone: 'warning' },
  STALE: { label: '갱신 필요', tone: 'warning' },
  RUNNING: { label: '수집 중', tone: 'running' },
  FAILED: { label: '수집 실패', tone: 'danger' },
  NO_DATA: { label: '수집 전', tone: 'muted' },
}

const DAILY_STATUS_META = {
  FRESH: '최신',
  WARNING: '일부 확인',
  STALE: '갱신 필요',
  NOT_AVAILABLE: '미생성',
}

export function dataStatusViewModel(data, { loading = false, error = false } = {}) {
  if (loading && !data) {
    return {
      label: '상태 확인 중',
      tone: 'muted',
      priceDate: '—',
      scoreDate: '—',
      runLabel: '확인 중',
      coverageLabel: '—',
      issueLabel: null,
      isRunning: false,
    }
  }

  if (error && !data) {
    return {
      label: '상태 확인 불가',
      tone: 'danger',
      priceDate: '—',
      scoreDate: '—',
      runLabel: '백엔드 연결 확인',
      coverageLabel: '—',
      issueLabel: null,
      isRunning: false,
    }
  }

  const status = STATUS_META[data?.status] ?? STATUS_META.NO_DATA
  const run = data?.latestRun
  const cadence = data?.schedulerCadence
  const expected = numberOrZero(data?.expectedTickerCount)
  const completed = numberOrZero(run?.successCount)
  const failed = numberOrZero(run?.failedCount)
  const skipped = numberOrZero(run?.skippedCount)
  const missingObservation = numberOrZero(
    data?.missingObservationTickerCount ?? data?.missingScoreTickerCount,
  )
  const issues = [
    failed > 0 ? `실패 ${failed}` : null,
    skipped > 0 ? `제외 ${skipped}` : null,
    missingObservation > 0 ? `S1 미산출 ${missingObservation}` : null,
  ].filter(Boolean)

  return {
    ...status,
    priceDate: formatObservedDate(data?.latestPriceDate),
    scoreDate: formatObservedDate(
      data?.latestObservationDate ?? data?.latestScoreDate,
    ),
    dailyScoreDate: formatObservedDate(data?.latestDailyObservationDate),
    dailyStatusLabel: DAILY_STATUS_META[data?.dailyObservationStatus]
      ?? '확인 불가',
    dailyCoverageLabel: numberOrZero(data?.expectedDailyObservationTickerCount) > 0
      ? `${numberOrZero(data?.freshDailyObservationTickerCount)}/${numberOrZero(data?.expectedDailyObservationTickerCount)} 종목`
      : '집계 없음',
    runLabel: schedulerRunLabel(run),
    coverageLabel: expected > 0 ? `${completed}/${expected} 종목` : '집계 없음',
    issueLabel: issues.length > 0 ? issues.join(' · ') : null,
    isRunning: run?.status === 'RUNNING',
    scheduleLabel: scheduleLabel(cadence),
    scheduleLocalLabel: scheduleLocalLabel(cadence),
    automationLabel: cadence?.requiresExternalProcess
      ? '로컬 스케줄러가 실행 중일 때 자동'
      : '서비스에서 자동 실행',
    manualRunLabel: cadence?.manualRunScope === 'FULL_TIER1'
      ? '가격·State S1·전향 관찰 전체'
      : '전체 데이터',
  }
}

export function scheduleLabel(cadence) {
  const time = cadence?.dailyTime
  const timezone = cadence?.timezone
  if (!time) return '예정 정보 없음'
  return `${time} ${timezone === 'America/New_York' ? 'ET' : timezone ?? ''}`.trim()
}

export function scheduleLocalLabel(cadence) {
  const value = cadence?.nextScheduledAt
  if (!value) return '다음 실행 시각 확인 불가'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '다음 실행 시각 확인 불가'
  return `다음 예정 · ${new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)}`
}

export function formatObservedDate(value) {
  if (!value) return '—'
  const parts = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/)
  return parts ? `${parts[1]}.${parts[2]}.${parts[3]}` : String(value)
}

export function schedulerRunLabel(run) {
  if (!run) return '실행 기록 없음'
  if (run.status === 'RUNNING') return '실행 중'
  const status = run.status === 'FAILED'
    ? '실패'
    : run.status === 'SUCCESS'
      ? '완료'
      : run.status === 'PARTIAL_FAILURE'
        ? '일부 실패'
        : run.status ?? '상태 없음'
  const timestamp = formatRunTimestamp(run.finishedAt ?? run.startedAt)
  return timestamp ? `${status} · ${timestamp}` : status
}

function numberOrZero(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function formatRunTimestamp(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}
