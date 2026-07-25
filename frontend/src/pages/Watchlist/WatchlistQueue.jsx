import HerdLens from '../../components/HerdLens/HerdLens'
import StockAvatar from '../../components/StockAvatar/StockAvatar'
import styles from './WatchlistQueue.module.css'

function formatDelta(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '—'
  const rounded = Math.round(numeric)
  return `${rounded > 0 ? '+' : ''}${rounded}`
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
}

export default function WatchlistQueue({
  watchlist,
  deletingTicker,
  onDelete,
  onOpenStock,
}) {
  return (
    <section className={styles.list} aria-label="관심종목 목록">
      <div className={styles.head} aria-hidden="true">
        <span>종목</span>
        <span>HERD · 4주</span>
        <span>변화</span>
        <span>관찰일</span>
        <span />
      </div>
      {watchlist.map((item) => {
        const deleting = deletingTicker === item.ticker
        const score = Number.isFinite(Number(item.herdScore))
          ? Number(item.herdScore)
          : null
        return (
          <article className={styles.row} key={item.ticker} data-deleting={deleting}>
            <button
              type="button"
              className={styles.openButton}
              onClick={() => onOpenStock(item.ticker)}
            >
              <span className={styles.identity}>
                <StockAvatar ticker={item.ticker} logoUrl={item.logoUrl} size="md" />
                <span>
                  <strong>{item.ticker}</strong>
                  <small>{item.companyName ?? item.memo ?? '관심종목'}</small>
                </span>
              </span>
              <HerdLens
                compact
                score={score}
                stage={item.herdStage}
                delta={item.delta4w}
              />
              <span className={styles.delta}>
                <strong>{formatDelta(item.delta4w)}</strong>
                <small>4주</small>
              </span>
              <span className={styles.date}>
                <strong>{formatDate(item.lastObservedSession ?? item.scoreDate)}</strong>
                <small>{item.freshnessStatus === 'STALE' ? '갱신 필요' : 'State S1'}</small>
              </span>
            </button>
            <button
              type="button"
              className={styles.deleteButton}
              disabled={Boolean(deletingTicker)}
              aria-label={`${item.ticker} 관심종목 삭제`}
              onClick={(event) => onDelete(event, item.ticker)}
            >
              {deleting ? '…' : '삭제'}
            </button>
          </article>
        )
      })}
    </section>
  )
}
