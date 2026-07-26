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
    return <div className={styles.dropdownPlaceholder} role="status">검색 중…</div>
  }
  if (result.status === 'not_found') {
    return (
      <div className={styles.dropdownPlaceholder} role="status">
        검색 결과가 없습니다. 티커를 직접 입력해보세요.
      </div>
    )
  }
  if (result.status === 'symbol_found') {
    return (
      <PendingSearchResult
        candidate={result.candidate}
        portfolioStatus={portfolioStatus}
        watchlistStatus={watchlistStatus}
        addError={addError}
        onAddPortfolio={onAddPortfolio}
        onAddWatchlist={onAddWatchlist}
        onOpen={onOpen}
      />
    )
  }

  const data = result.data
  const badge = stageBadgeStyle(data.herdStage)
  const meta = result.matches?.find((item) => item.ticker === data.ticker) ??
    TICKER_META[data.ticker]
  return (
    <article className={styles.searchResultItem}>
      <button
        type="button"
        className={styles.resultOpen}
        onClick={() => onOpen(data.ticker)}
        aria-label={`${data.ticker} 종목 상세 열기`}
      >
        <span className={styles.resultLeft}>
          <StockAvatar ticker={data.ticker} logoUrl={data.logoUrl} tone={badge} />
          <span>
            <strong className={styles.resultTicker}>{data.ticker}</strong>
            <span className={styles.resultName}>
              {meta ? `${meta.name} · ${meta.sector}` : '미국 주식'}
            </span>
          </span>
        </span>
      </button>

      <div className={styles.resultRight}>
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
        {addError && <div className={styles.resultError} role="alert">{addError}</div>}
      </div>
    </article>
  )
}

function PendingSearchResult({
  candidate,
  portfolioStatus,
  watchlistStatus,
  addError,
  onAddPortfolio,
  onAddWatchlist,
  onOpen,
}) {
  return (
    <article className={styles.searchResultItem}>
      <button
        type="button"
        className={styles.resultOpen}
        onClick={() => onOpen(candidate.ticker)}
        aria-label={`${candidate.ticker} 종목 상세 열기`}
      >
        <span className={styles.resultLeft}>
          <StockAvatar ticker={candidate.ticker} />
          <span>
            <strong className={styles.resultTicker}>{candidate.ticker}</strong>
            <span className={styles.resultName}>
              {candidate.name} · {candidate.sector}
            </span>
            <span className={styles.resultNote}>
              State S1 관찰 준비 중
            </span>
          </span>
        </span>
      </button>
      <div className={styles.resultRight}>
        <HerdLens compact score={null} />
        <AddButton
          status={portfolioStatus}
          idleLabel="+ 포트폴리오"
          onClick={() => onAddPortfolio(candidate.ticker)}
        />
        <AddButton
          status={watchlistStatus}
          idleLabel="+ 관심종목"
          onClick={() => onAddWatchlist(candidate.ticker)}
        />
        {addError && <div className={styles.resultError} role="alert">{addError}</div>}
      </div>
    </article>
  )
}

function formatDelta(value) {
  if (value == null || value === '') return '4주 —'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '4주 —'
  const rounded = Math.round(numeric)
  return `4주 ${rounded > 0 ? '+' : ''}${rounded}`
}

function AddButton({ status, idleLabel, onClick }) {
  const complete = status === 'added' || status === 'exists'
  return (
    <button
      type="button"
      className={`${styles.resultAddBtn} ${complete ? styles.resultAddBtnDone : ''}`}
      onClick={onClick}
      disabled={status === 'loading'}
    >
      {addButtonLabel(status, idleLabel)}
    </button>
  )
}
