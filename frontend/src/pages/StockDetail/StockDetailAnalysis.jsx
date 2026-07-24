import styles from './StockDetail.module.css'

const S1_FAMILIES = [
  ['priceExtension', '가격 확장'],
  ['trendPosition', '추세 위치'],
  ['relativePosition', '상대 위치'],
  ['participation', '시장 참여'],
]

function safeRounded(value) {
  const number = Number(value)
  return Number.isFinite(number) ? Math.round(number) : '—'
}

function ObservationCard({ observation, color }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <div className={styles.cardTitle}>State S1 관측값</div>
          <div className={styles.cardMeta}>고정된 네 관찰 가족 · 동일 비중</div>
        </div>
        <div className={styles.cardMeta}>
          {observation.lastObservedSession} 기준
        </div>
      </div>
      <div className={styles.cardBody}>
        {S1_FAMILIES.map(([key, label]) => {
          const value = Number(observation.families?.[key])
          const available = Number.isFinite(value)
          return (
            <div key={key} className={styles.indicatorRow}>
              <div className={styles.indicatorLabel}>{label}</div>
              <div className={styles.indicatorWeight}>25%</div>
              <div className={styles.indicatorTrack}>
                {available && (
                  <div
                    className={styles.indicatorFill}
                    style={{
                      width: `${Math.max(0, Math.min(100, value))}%`,
                      background: color,
                    }}
                  />
                )}
              </div>
              <div className={styles.indicatorValue}>
                {available ? Math.round(value) : '—'}
              </div>
            </div>
          )
        })}
        <div className={styles.adjustmentBox}>
          <div className={styles.adjustmentRow}>
            <span>상태 전환</span>
            <strong>{observation.transition ?? 'NEUTRAL'}</strong>
          </div>
          <div className={styles.adjustmentRow}>
            <span>하방 위험 맥락</span>
            <strong>{safeRounded(observation.downsideRiskContext)}</strong>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function StockDetailAnalysis({ observation, color }) {
  return (
    <details className={styles.detailDisclosure}>
      <summary>
        <div><span>상세 관찰</span><strong>State S1 구성값</strong></div>
        <em>펼쳐보기</em>
      </summary>
      <div className={styles.detailDisclosureBody}>
        <ObservationCard observation={observation} color={color} />
      </div>
    </details>
  )
}
