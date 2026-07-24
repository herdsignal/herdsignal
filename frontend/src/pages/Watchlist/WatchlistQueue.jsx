import StockAvatar from '../../components/StockAvatar/StockAvatar'
import {
  actionBasisLabel,
  actionIntensityLabel,
  formatActionScore,
} from '../../utils/actionIntensity'
import { signalDesc } from '../../utils/decision'
import { stageBadgeStyle, stageColor } from '../../utils/herdStage'
import { formatSignalAgeLabel, formatSignalDuration } from '../../utils/signalDuration'
import { signalStyle } from '../../utils/signalStyle'
import { operationalSignal } from '../../utils/portfolioTools'
import sharedStyles from './Watchlist.module.css'
import componentStyles from './WatchlistQueue.module.css'

const styles = { ...sharedStyles, ...componentStyles }

export default function WatchlistQueue({
  watchlist,
  scoredWatchlist,
  observationQueue,
  deletingTicker,
  onDelete,
  onOpenStock,
}) {
  const readyCount = scoredWatchlist.filter((item) => item.queueState === 'READY').length
  const waitCount = watchlist.filter((item) => operationalSignal(item) === 'HOLD').length
  const sellWatchCount = watchlist.filter(
    (item) => ['Herd Drift', 'Herd Rush'].includes(item.herdStage)
  ).length

  return (
    <>
      <div className={styles.watchSummary}>
        <Summary label="Ready" value={readyCount} detail="우선 확인 후보" />
        <Summary label="Observe" value={waitCount} detail="보유·관찰 구간" />
        <Summary label="Overheat" value={sellWatchCount} detail="쏠림·밀집 후보" />
      </div>

      <div className={styles.opportunityPanel}>
        <SectionHeader title="우선 관찰" hint="상태 변화·밀집도 기준" />
        {observationQueue.length > 0 ? (
          <div className={styles.opportunityList}>
            {observationQueue.map((item, index) => (
              <button
                key={item.ticker}
                className={styles.opportunityItem}
                onClick={() => onOpenStock(item.ticker)}
              >
                <span>{index + 1}</span>
                <strong>{item.ticker}</strong>
                <em>{formatActionCode(item)}</em>
                <small style={{ color: signalStyle(item.signal).color }}>
                  {item.queueLabel} · {actionBasisLabel(item)} · HERD {Math.round(item.herdScore)}
                  {formatSignalDuration(item) ? ` · ${formatSignalAgeLabel(item)}` : ''}
                </small>
              </button>
            ))}
          </div>
        ) : <div className={styles.opportunityEmpty}>관찰할 종목이 없습니다.</div>}
      </div>

      <SectionHeader title={`관찰 종목 · ${watchlist.length}`} hint="준비도 높은 순" />

      <div className={styles.queueTable}>
        <div className={styles.queueHead}>
          <span>종목</span><span>HERD</span><span>행동</span><span>관찰 상태</span><span>업데이트</span>
        </div>
        {scoredWatchlist.map((item) => (
          <QueueRow
            key={item.ticker}
            item={item}
            deletingTicker={deletingTicker}
            onDelete={onDelete}
            onOpenStock={onOpenStock}
          />
        ))}
      </div>
    </>
  )
}

function Summary({ label, value, detail }) {
  return <div><span>{label}</span><strong>{value}개</strong><em>{detail}</em></div>
}

function SectionHeader({ title, hint }) {
  return <div className={styles.sectionRow}><div className={styles.sectionTitle}>{title}</div><div className={styles.sectionHint}>{hint}</div></div>
}

function QueueRow({ item, deletingTicker, onDelete, onOpenStock }) {
  const color = stageColor(item.herdStage)
  const action = operationalSignal(item)
  const signal = signalStyle(action)
  const stageName = item.herdStage?.startsWith('Herd ')
    ? item.herdStage.slice(5)
    : item.herdStage ?? '관찰 준비 중'
  const score = Number.isFinite(Number(item.herdScore))
    ? Math.round(Number(item.herdScore))
    : null
  const isDeleting = deletingTicker === item.ticker

  return (
    <div
      className={styles.queueRow}
      onClick={() => onOpenStock(item.ticker)}
      style={{ opacity: isDeleting ? 0.4 : 1 }}
    >
      <span className={styles.queueStripe} style={{ background: color, color }} />
      <div className={styles.queueStock}>
        <StockAvatar ticker={item.ticker} logoUrl={item.logoUrl} tone={stageBadgeStyle(item.herdStage)} />
        <div>
          <strong>{item.ticker}</strong>
          <em style={{ color }}>
            {stageName}{score == null ? '' : ` · 상태 위치 ${score}`}
          </em>
        </div>
      </div>
      <div className={styles.queueHerd}>
        <strong style={{ color }}>{score ?? '—'}</strong>
        <span>{stageName}</span>
      </div>
      <div className={styles.queueAction}>
        <strong style={{ color: signal.color }}>{formatActionCode(item)}</strong>
        <span>{formatActionText(item)}</span>
      </div>
      <div className={styles.queueSignal}>
        <strong>{item.queueLabel}</strong>
        <span>{item.queueDetail} · {formatSignalAgeLabel(item)}</span>
      </div>
      <div className={styles.queueMeta}>
        <strong>{formatDate(item.scoreDate)}</strong>
        <span>State S1</span>
      </div>
      <button
        className={styles.queueDeleteBtn}
        onClick={(event) => onDelete(event, item.ticker)}
        disabled={Boolean(deletingTicker)}
        title={`${item.ticker} 관심 종목에서 삭제`}
      >
        {isDeleting ? '…' : '✕'}
      </button>
    </div>
  )
}

function formatActionText(item) {
  const signal = operationalSignal(item)
  const authorized = item?.actionAuthorized === true && signal !== 'HOLD'
  const action = authorized ? (item?.actionLabel ?? signalDesc(signal)) : signalDesc('HOLD')
  return [authorized ? formatActionScore(item?.actionScore) : null, actionIntensityLabel(item), action]
    .filter(Boolean)
    .join(' · ')
}

function formatActionCode(item) {
  const signal = operationalSignal(item)
  const intensity = actionIntensityLabel(item)
  return intensity === '관찰' ? signal : `${signal} · ${intensity}`
}

function formatDate(dateString) {
  if (!dateString) return '—'
  const date = new Date(dateString)
  return Number.isNaN(date.getTime())
    ? dateString
    : date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}
