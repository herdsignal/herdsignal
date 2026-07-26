import styles from './Portfolio.module.css'

function percent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—'
}

export default function PortfolioExposure({ exposure }) {
  const sectors = exposure?.sectors ?? []
  return (
    <section className={styles.exposureSection} aria-labelledby="exposure-title">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="exposure-title">비중·노출</h2>
          <span>직접 보유 기준</span>
        </div>
      </div>
      <div className={styles.exposureSummary}>
        <div>
          <span>최대 종목</span>
          <strong>{exposure?.topHolding?.ticker ?? '—'}</strong>
          <small>{percent(exposure?.topHolding?.weightPct)}</small>
        </div>
        <div>
          <span>상위 3종목</span>
          <strong>{percent(exposure?.topThreeWeightPct)}</strong>
          <small>전체 자산 기준</small>
        </div>
        <div>
          <span>최대 섹터</span>
          <strong>{exposure?.largestSector?.name ?? '—'}</strong>
          <small>{percent(exposure?.largestSector?.weightPct)}</small>
        </div>
        <div>
          <span>현금</span>
          <strong>{percent(exposure?.cashWeightPct)}</strong>
          <small>전체 자산 기준</small>
        </div>
      </div>
      {sectors.length > 0 && (
        <div className={styles.sectorExposure}>
          {sectors.slice(0, 6).map((sector) => (
            <div key={sector.name}>
              <span>{sector.name}</span>
              <i>
                <b style={{ width: `${Math.min(100, sector.weightPct)}%` }} />
              </i>
              <strong>{percent(sector.weightPct)}</strong>
            </div>
          ))}
        </div>
      )}
      <p className={styles.exposureNote}>
        현금 포함 전체 자산 기준 · ETF 내부 섹터 구성 미반영 · 위험 등급 아님
      </p>
    </section>
  )
}
