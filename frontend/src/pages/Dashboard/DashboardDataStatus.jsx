import { fmtAxisDate } from './dashboardModel'
import styles from './Dashboard.module.css'

const STATUS_LABEL = {
  FRESH: '최신',
  WARNING: '확인 필요',
  STALE: '업데이트 필요',
  RUNNING: '업데이트 중',
  NO_DATA: '실행 이력 없음',
}

function formatRunTime(value) {
  if (!value) return null
  const date = new Date(`${value}Z`)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString('ko-KR', {
    month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

export default function DashboardDataStatus({ status, failed }) {
  if (failed) {
    return (
      <div className={`${styles.dataStatusBar} ${styles.dataStatusUnknown}`} role="status">
        <strong>상태 확인 불가</strong>
        <span>데이터 갱신 상태 API에 연결할 수 없습니다.</span>
      </div>
    )
  }
  if (!status) return null

  const tone = styles[`dataStatus${status.status}`] ?? styles.dataStatusUnknown
  const run = status.latestRun
  const runTime = formatRunTime(run?.finishedAt ?? run?.startedAt)

  return (
    <div className={`${styles.dataStatusBar} ${tone}`} role="status">
      <strong>{STATUS_LABEL[status.status] ?? '상태 확인'}</strong>
      <span>
        가격 {status.latestPriceDate ? fmtAxisDate(status.latestPriceDate) : '—'}
        {' · '}HERD {status.latestScoreDate ? fmtAxisDate(status.latestScoreDate) : '—'}
        {runTime && ` · 마지막 수집 ${runTime}`}
      </span>
      {run && (
        <em>
          {run.successCount}/{run.totalCount} 성공
          {run.failedCount > 0 && ` · 실패 ${run.failedCount}개`}
          {run.failedTickers?.length > 0 && ` (${run.failedTickers.join(', ')})`}
        </em>
      )}
    </div>
  )
}
