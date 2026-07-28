import MarketField from '../MarketField/MarketField'
import styles from './HerdObservationPanel.module.css'

function formatDate(value) {
  if (!value) return '기준일 없음'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function formatDelta(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '4W —'
  return `4W ${numeric > 0 ? '+' : ''}${numeric.toFixed(1)}`
}

export default function HerdObservationPanel({
  ticker,
  name,
  scopeLabel = 'STOCK OBSERVATION',
  score,
  stage,
  delta4w,
  observationDate,
  freshness = '주간 관찰',
  loading = false,
  unavailable = false,
  error = false,
  actions = null,
  compact = false,
  condensed = false,
}) {
  return (
    <section
      className={`${styles.panel} ${compact ? styles.compact : ''}`}
      aria-labelledby="herd-observation-title"
    >
      <header className={styles.header}>
        <div>
          <span>{scopeLabel}</span>
          <h2 id="herd-observation-title">{ticker}</h2>
          <p>{name}</p>
        </div>
        <div className={styles.meta}>
          <strong>{formatDate(observationDate)}</strong>
          <span>{freshness} · {formatDelta(delta4w)}</span>
        </div>
      </header>

      {loading
        ? <div className={styles.loading} role="status">HERD 관찰값 불러오는 중</div>
        : (
          <MarketField
            score={unavailable ? null : score}
            stage={unavailable ? null : stage}
            momentum={delta4w}
            compact={compact}
            condensed={condensed}
          />
          )}

      {!loading && (unavailable || error) && (
        <p className={styles.notice} role="status">
          {error
            ? `${ticker} 관찰값을 불러오지 못했습니다.`
            : `${ticker} 관찰값을 준비하고 있습니다.`}
        </p>
      )}

      {actions && <footer className={styles.actions}>{actions}</footer>}
    </section>
  )
}
