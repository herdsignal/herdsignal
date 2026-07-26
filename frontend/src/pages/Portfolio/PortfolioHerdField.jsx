import styles from './Portfolio.module.css'

const STAGE_POSITIONS = [
  { stage: 'Flee', position: 7.5 },
  { stage: 'Scatter', position: 27.5 },
  { stage: 'Calm', position: 50 },
  { stage: 'Drift', position: 67.5 },
  { stage: 'Rush', position: 87.5 },
]

function percent(value, digits = 0) {
  return Number.isFinite(Number(value))
    ? `${Number(value).toFixed(digits)}%`
    : '—'
}

export default function PortfolioHerdField({ field, onOpenStock }) {
  const points = field?.points ?? []
  const hasObservations = points.length > 0

  return (
    <section className={styles.herdFieldSection} aria-labelledby="portfolio-herd-title">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="portfolio-herd-title">보유 HERD Field</h2>
          <span>관찰 가능 종목 평가액 기준</span>
        </div>
        <div className={styles.fieldCoverage}>
          <span>관찰 {field?.observedCount ?? 0}/{field?.totalCount ?? 0}</span>
          <strong>평가액 {percent(field?.observedValueCoveragePct)}</strong>
        </div>
      </div>

      {!hasObservations ? (
        <p className={styles.fieldEmpty}>HERD 관찰값이 있는 보유 종목이 없습니다.</p>
      ) : (
        <>
          <div className={styles.fieldBody}>
            <div className={styles.fieldAggregate}>
              <span>가중 위치</span>
              <strong>{Math.round(field.weightedScore)}</strong>
              <small>{field.weightedStage}</small>
            </div>
            <div className={styles.portfolioField} aria-label="보유 종목 HERD 위치">
              <div className={styles.fieldTrack} aria-hidden="true" />
              {STAGE_POSITIONS.map(({ stage, position }) => (
                <span
                  className={styles.fieldStageLabel}
                  key={stage}
                  style={{ '--field-x': `${position}%` }}
                >
                  {stage}
                </span>
              ))}
              {points.map((point) => (
                <button
                  type="button"
                  className={styles.fieldPoint}
                  key={point.ticker}
                  style={{
                    '--field-x': `${Math.max(1.5, Math.min(98.5, point.score))}%`,
                    '--field-y': `${22 + point.lane * 17}%`,
                    '--field-size': `${Math.max(
                      9,
                      Math.min(21, 8 + Math.sqrt(point.observedWeightPct) * 1.7),
                    )}px`,
                  }}
                  aria-label={`${point.ticker} HERD ${Math.round(point.score)}, ${point.stage}, 보유 주식 중 ${percent(point.observedWeightPct, 1)}`}
                  onClick={() => onOpenStock(point.ticker)}
                >
                  <i />
                  <span>{point.ticker}</span>
                </button>
              ))}
            </div>
          </div>

          <p className={styles.fieldNote}>
            점 크기: 보유 주식 내 평가액 · 현금 제외 · 개인 목표 비중 미반영
          </p>
        </>
      )}
    </section>
  )
}
