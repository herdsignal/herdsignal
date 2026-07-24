import StockAvatar from '../../components/StockAvatar/StockAvatar'
import { stageBadgeStyle, stageColor } from '../../utils/herdStage'
import {
  TICKER_META,
  addButtonLabel,
  herdReadiness,
  inclusionDecision,
  stageDisplay,
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
  const readiness = herdReadiness(data)
  const decision = inclusionDecision(data)
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
        <div className={styles.resultHerd}>
          <div
            className={styles.resultHerdScore}
            style={{ color: stageColor(data.herdStage) }}
          >
            {Math.round(data.herdV4 ?? data.herdScore)}
          </div>
          <div className={`${styles.readinessPill} ${styles[`readiness${readiness.tone}`]}`}>
            {readiness.label}
          </div>
          <div className={styles.resultHerdDesc}>
            {stageDisplay(data.herdStage)} · {readiness.desc}
          </div>
        </div>
        <Decision decision={decision} />
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
  const readiness = herdReadiness(null)
  const decision = inclusionDecision(null)
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
            심볼은 찾았지만 HERD 데이터는 아직 없습니다. 상장 기간이 짧거나 계산 대기 중일 수 있어요.
          </div>
        </div>
      </div>
      <div className={styles.resultRight}>
        <div className={styles.resultHerd}>
          <div className={styles.resultHerdScore}>—</div>
          <div className={`${styles.readinessPill} ${styles.readinessPending}`}>
            {readiness.label}
          </div>
          <div className={styles.resultHerdDesc}>{readiness.desc}</div>
        </div>
        <Decision decision={decision} />
        <button className={`${styles.resultAddBtn} ${styles.resultAddBtnBlocked}`} disabled>
          HERD 필요
        </button>
        <button className={`${styles.resultAddBtn} ${styles.resultAddBtnBlocked}`} disabled>
          HERD 필요
        </button>
      </div>
    </div>
  )
}

function Decision({ decision }) {
  return (
    <div className={`${styles.resultDecision} ${styles[`decision${decision.tone}`]}`}>
      <span>편입 판단</span>
      <strong>{decision.label}</strong>
      <em>{decision.desc}</em>
    </div>
  )
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
