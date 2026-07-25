import MarketField from '../../components/MarketField/MarketField'
import { resolvePreviousScore } from '../../components/HerdLens/herdLensModel'
import styles from './StockDetail.module.css'

function signed(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '—'
  const rounded = Math.round(numeric)
  return `${rounded > 0 ? '+' : ''}${rounded}`
}

export default function StockDetailHero({
  observation,
  herdScore,
  herdStage,
}) {
  const previous = resolvePreviousScore(herdScore, null, observation.delta4w)

  return (
    <section className={styles.stateSection} aria-labelledby="stock-state-title">
      <div className={styles.stateHeader}>
        <div>
          <span>HERD State S1</span>
          <h2 id="stock-state-title">현재 군중 상태</h2>
        </div>
        <dl className={styles.stateMeta}>
          <div><dt>4주 전</dt><dd>{previous == null ? '—' : Math.round(previous)}</dd></div>
          <div><dt>4주 변화</dt><dd>{signed(observation.delta4w)}</dd></div>
          <div><dt>전환</dt><dd>{observation.transition ?? '—'}</dd></div>
          <div>
            <dt>관찰일</dt>
            <dd>{observation.lastObservedSession ?? observation.observationDate ?? '—'}</dd>
          </div>
        </dl>
      </div>
      <MarketField compact score={herdScore} stage={herdStage} />
    </section>
  )
}
