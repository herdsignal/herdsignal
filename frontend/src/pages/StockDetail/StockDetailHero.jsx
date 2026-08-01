import MarketField from '../../components/MarketField/MarketField'
import styles from './StockDetail.module.css'

function signed(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '—'
  const rounded = Math.round(numeric)
  return `${rounded > 0 ? '+' : ''}${rounded}`
}

export default function StockDetailHero({
  herdScore,
  herdStage,
  displayHerdScore,
  displayHerdStage,
  dailyObservation,
  dailyObservationAvailable,
  stateSummary,
}) {
  const transition = stateSummary.recentTransition
  const displayDate = dailyObservationAvailable
    ? dailyObservation?.lastObservedSession
    : stateSummary.currentDate
  const nowcastDelta = dailyObservationAvailable
    ? Number(displayHerdScore) - Number(herdScore)
    : null

  return (
    <section id="stock-state" className={styles.stateSection} aria-labelledby="stock-state-title">
      <div className={styles.stateHeader}>
        <div>
          <span>
            {dailyObservationAvailable
              ? 'HERD DAILY NOWCAST'
              : 'HERD WEEKLY CONFIRMED'}
          </span>
          <h2 id="stock-state-title">현재 군중 상태</h2>
          <small className={styles.observationDate}>
            {displayDate ?? '—'} {dailyObservationAvailable ? '일간 잠정' : '주간 확정'}
          </small>
        </div>
        <dl className={styles.stateMeta}>
          <div>
            <dt>일간–주간</dt>
            <dd>{nowcastDelta == null ? '—' : signed(nowcastDelta)}</dd>
            <small>{dailyObservationAvailable ? '잠정 편차' : '일간 관찰 없음'}</small>
          </div>
          <div>
            <dt>4주 비교</dt>
            <dd>{stateSummary.fourWeekComparison}</dd>
          </div>
          <div>
            <dt>4주 변화</dt>
            <dd>{signed(stateSummary.fourWeekDelta)}</dd>
          </div>
          <div>
            <dt>주간 확정</dt>
            <dd>{Math.round(herdScore)} · {herdStage}</dd>
            <small>
              {stateSummary.currentDate ?? '—'} · {stateSummary.stageDurationLabel}
            </small>
          </div>
          <div>
            <dt>최근 전환</dt>
            <dd>{transition?.label ?? '최근 전환 없음'}</dd>
            {transition?.date && <small>{transition.date}</small>}
          </div>
        </dl>
      </div>
      <MarketField
        compact
        score={displayHerdScore}
        stage={displayHerdStage}
      />
    </section>
  )
}
