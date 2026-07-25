import HerdLens from '../../components/HerdLens/HerdLens'
import StockAvatar from '../../components/StockAvatar/StockAvatar'
import { stageBadgeStyle } from '../../utils/herdStage'
import {
  TICKER_META,
  addButtonLabel,
} from './searchModel'
import styles from './Search.module.css'

export default function SearchResultContent({
  result,
  portfolioStatus,
  watchlistStatus,
  addError,
  onAddPortfolio,
  onAddWatchlist,
  onOpen,
}) {
  if (result.status === 'loading') {
    return <div className={styles.dropdownPlaceholder}>검색 중…</div>
  }
  if (result.status === 'not_found') {
    return (
      <div className={styles.dropdownPlaceholder}>
        검색 결과가 없습니다. 티커를 직접 입력해보세요.
      </div>
    )
  }
  if (result.status === 'symbol_found') {
    return <PendingSearchResult candidate={result.candidate} />
  }

  const data = result.data
  const badge = stageBadgeStyle(data.herdStage)
  const meta = result.matches?.find((item) => item.ticker === data.ticker) ??
    TICKER_META[data.ticker]
  return (
    <div className={styles.searchResultItem} onClick={() => onOpen(data.ticker)}>
      <div className={styles.resultLeft}>
        <StockAvatar ticker={data.ticker} logoUrl={data.logoUrl} tone={badge} />
        <div>
          <div className={styles.resultTicker}>{data.ticker}</div>
          <div className={styles.resultName}>
            {meta ? `${meta.name} · ${meta.sector}` : '미국 주식'}
          </div>
        </div>
      </div>

      <div className={styles.resultRight} onClick={(event) => event.stopPropagation()}>
        <HerdLens
          compact
          score={data.herdScore}
          stage={data.herdStage}
          delta={data.delta4w}
        />
        <span className={styles.observationMeta}>
          <strong>{formatDelta(data.delta4w)}</strong>
          <small>{data.freshnessStatus === 'STALE' ? '갱신 필요' : data.scoreDate ?? 'State S1'}</small>
        </span>
        <AddButton
          status={portfolioStatus}
          idleLabel="+ 포트폴리오"
          onClick={() => onAddPortfolio(data.ticker)}
        />
        <AddButton
          status={watchlistStatus}
          idleLabel="+ 관심종목"
          onClick={() => onAddWatchlist(data.ticker)}
        />
        {addError && <div className={styles.resultError}>{addError}</div>}
      </div>
    </div>
  )
}

function PendingSearchResult({ candidate }) {
  return (
    <div className={styles.searchResultItem}>
      <div className={styles.resultLeft}>
        <StockAvatar ticker={candidate.ticker} />
        <div>
          <div className={styles.resultTicker}>{candidate.ticker}</div>
          <div className={styles.resultName}>
            {candidate.name} · {candidate.sector}
          </div>
          <div className={styles.resultNote}>
            State S1 관찰값 없음
          </div>
        </div>
      </div>
      <div className={styles.resultRight}>
        <HerdLens compact score={null} />
        <button className={`${styles.resultAddBtn} ${styles.resultAddBtnBlocked}`} disabled>
          관찰값 필요
        </button>
        <button className={`${styles.resultAddBtn} ${styles.resultAddBtnBlocked}`} disabled>
          관찰값 필요
        </button>
      </div>
    </div>
  )
}

function formatDelta(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '4주 —'
  const rounded = Math.round(numeric)
  return `4주 ${rounded > 0 ? '+' : ''}${rounded}`
}

function AddButton({ status, idleLabel, onClick }) {
  const complete = status === 'added' || status === 'exists'
  return (
    <button
      className={`${styles.resultAddBtn} ${complete ? styles.resultAddBtnDone : ''}`}
      onClick={onClick}
      disabled={status === 'loading'}
    >
      {addButtonLabel(status, idleLabel)}
    </button>
  )
}
