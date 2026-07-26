const STATUS_META = {
  FRESH: { label: '데이터 최신', tone: 'fresh' },
  WARNING: { label: '일부 확인', tone: 'warning' },
  STALE: { label: '갱신 필요', tone: 'warning' },
  RUNNING: { label: '수집 중', tone: 'running' },
  FAILED: { label: '수집 실패', tone: 'danger' },
  NO_DATA: { label: '수집 전', tone: 'muted' },
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
  const expected = numberOrZero(data?.expectedTickerCount)
  const completed = numberOrZero(run?.successCount)
  const failed = numberOrZero(run?.failedCount)
  const skipped = numberOrZero(run?.skippedCount)
  const missingPrice = numberOrZero(data?.missingPriceTickerCount)
  const missingObservation = numberOrZero(
    data?.missingObservationTickerCount ?? data?.missingScoreTickerCount,
  )
  const issues = [
    failed > 0 ? `실패 ${failed}` : null,
    skipped > 0 ? `제외 ${skipped}` : null,
    missingPrice > 0 ? `가격 미수집 ${missingPrice}` : null,
    missingObservation > 0 ? `S1 미산출 ${missingObservation}` : null,
  ].filter(Boolean)

  return {
    ...status,
    priceDate: formatObservedDate(data?.latestPriceDate),
    scoreDate: formatObservedDate(
      data?.latestObservationDate ?? data?.latestScoreDate,
    ),
    runLabel: schedulerRunLabel(run),
    coverageLabel: expected > 0 ? `${completed}/${expected} 종목` : '집계 없음',
    issueLabel: issues.length > 0 ? issues.join(' · ') : null,
    isRunning: run?.status === 'RUNNING',
  }
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
