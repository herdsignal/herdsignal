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
  stateSummary,
}) {
  const transition = stateSummary.recentTransition

  return (
    <section id="stock-state" className={styles.stateSection} aria-labelledby="stock-state-title">
      <div className={styles.stateHeader}>
        <div>
          <span>HERD WEEKLY OBSERVATION</span>
          <h2 id="stock-state-title">현재 군중 상태</h2>
          <small className={styles.observationDate}>
            {stateSummary.currentDate ?? '—'} 관찰
          </small>
        </div>
        <dl className={styles.stateMeta}>
          <div>
            <dt>4주 비교</dt>
            <dd>{stateSummary.fourWeekComparison}</dd>
          </div>
          <div>
            <dt>4주 변화</dt>
            <dd>{signed(stateSummary.fourWeekDelta)}</dd>
          </div>
          <div>
            <dt>현재 단계</dt>
            <dd>{stateSummary.stageLabel} · {stateSummary.stageDurationLabel}</dd>
          </div>
          <div>
            <dt>최근 전환</dt>
            <dd>{transition?.label ?? '최근 전환 없음'}</dd>
            {transition?.date && <small>{transition.date}</small>}
          </div>
        </dl>
      </div>
      <MarketField compact score={herdScore} stage={herdStage} />
    </section>
  )
}
