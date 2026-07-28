import styles from './StockDetail.module.css'

const S1_FAMILIES = [
  ['priceExtension', '가격 확장'],
  ['trendPosition', '추세 위치'],
  ['relativePosition', '상대 위치'],
  ['participation', '시장 참여'],
]

function bounded(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric)) : null
}

export default function StockDetailAnalysis({ observation, color }) {
  const risk = bounded(observation.downsideRiskContext)

  return (
    <section id="stock-evidence" className={styles.evidenceSection} aria-labelledby="stock-evidence-title">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="stock-evidence-title">HERD 구성</h2>
          <span>State S1 · 각 25%</span>
        </div>
        <span>{observation.lastObservedSession ?? '—'} 기준</span>
      </div>
      <div className={styles.evidenceGrid}>
        {S1_FAMILIES.map(([key, label]) => {
          const value = bounded(observation.families?.[key])
          return (
            <div className={styles.evidenceItem} key={key}>
              <span>{label}</span>
              <strong>{value == null ? '—' : Math.round(value)}</strong>
              <i aria-hidden="true">
                {value != null && (
                  <b style={{ width: `${value}%`, background: color }} />
                )}
              </i>
            </div>
          )
        })}
      </div>
      <div className={styles.riskContext}>
        <span>하방 위험 맥락</span>
        <i aria-hidden="true">
          {risk != null && <b style={{ width: `${risk}%` }} />}
        </i>
        <strong>{risk == null ? '—' : Math.round(risk)}</strong>
      </div>
    </section>
  )
}
