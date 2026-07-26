import { useState } from 'react'
import { Link } from 'react-router-dom'
import { historyChartGeometry } from './portfolioModel'
import styles from './Portfolio.module.css'

const PERIODS = [
  { value: 'month', label: '1개월' },
  { value: 'year', label: '1년' },
  { value: 'all', label: '전체' },
]

function signedPct(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  const numeric = Number(value)
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(1)}%`
}

export default function PortfolioHistory({
  points,
  period,
  periodLabel,
  accountValueChangePct,
  loading,
  error,
  displayAmount,
  privacyMode,
  onPeriodChange,
}) {
  const [activeIndex, setActiveIndex] = useState(null)
  const geometry = historyChartGeometry(points)
  const change = accountValueChangePct == null ? null : Number(accountValueChangePct)
  const tone = change == null || !Number.isFinite(change)
    ? ''
    : change >= 0 ? styles.positive : styles.negative
  const selectedIndex = activeIndex ?? Math.max(0, points.length - 1)
  const selectedPoint = points[selectedIndex] ?? null
  const selectedCoordinate = geometry.coordinates[selectedIndex] ?? null

  function selectNearestPoint(event) {
    if (points.length === 0) return
    const bounds = event.currentTarget.getBoundingClientRect()
    const ratio = bounds.width > 0
      ? Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width))
      : 1
    setActiveIndex(Math.round(ratio * (points.length - 1)))
  }

  return (
    <section className={styles.historySection} aria-labelledby="asset-history-title">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="asset-history-title">계좌 가치</h2>
          <span>입출금 포함 · {periodLabel}</span>
        </div>
        <div className={styles.historyControls}>
          <div className={styles.periodTabs} aria-label="계좌 가치 기간">
            {PERIODS.map((item) => (
              <button
                type="button"
                key={item.value}
                className={period === item.value ? styles.activeTab : ''}
                aria-pressed={period === item.value}
                onClick={() => onPeriodChange(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <Link className={styles.historyDetailLink} to="/history">
            상세 보기
          </Link>
        </div>
      </div>

      <div className={styles.historyBody}>
        <div className={styles.chartSummary}>
          <span>{periodLabel} 변화</span>
          <strong className={tone}>{signedPct(accountValueChangePct)}</strong>
          <small>입출금 포함 · 투자 수익률 아님</small>
        </div>

        <div
          className={styles.chartFrame}
          onPointerMove={selectNearestPoint}
          onPointerLeave={() => setActiveIndex(null)}
        >
          {loading && <p role="status">히스토리 불러오는 중…</p>}
          {!loading && error && <p role="alert">{error}</p>}
          {!loading && !error && !geometry.path && (
            <p>아직 자산 기록이 없습니다.</p>
          )}
          {!loading && !error && geometry.path && (
            <svg
              viewBox="0 0 1000 220"
              preserveAspectRatio="none"
              role="img"
              aria-label={`${periodLabel} 계좌 가치 변화`}
            >
              <defs>
                <linearGradient id="portfolio-area" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--hs-scatter)" stopOpacity=".18" />
                  <stop offset="100%" stopColor="var(--hs-scatter)" stopOpacity="0" />
                </linearGradient>
              </defs>
              {[55, 110, 165].map((y) => (
                <line
                  key={y}
                  x1="0"
                  x2="1000"
                  y1={y}
                  y2={y}
                  className={styles.chartGrid}
                  vectorEffect="non-scaling-stroke"
                />
              ))}
              <path d={geometry.areaPath} fill="url(#portfolio-area)" />
              <path
                d={geometry.path}
                fill="none"
                stroke="var(--hs-scatter)"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
              {selectedCoordinate && (
                <>
                  <line
                    x1={selectedCoordinate[0]}
                    x2={selectedCoordinate[0]}
                    y1="0"
                    y2="220"
                    className={styles.chartCursor}
                    vectorEffect="non-scaling-stroke"
                  />
                  <circle
                    cx={selectedCoordinate[0]}
                    cy={selectedCoordinate[1]}
                    r="4"
                    className={styles.chartPoint}
                    vectorEffect="non-scaling-stroke"
                  />
                </>
              )}
            </svg>
          )}
          {!loading && !error && selectedPoint && selectedCoordinate && (
            <div
              className={styles.chartTooltip}
              style={{
                left: `${Math.max(7, Math.min(93, selectedCoordinate[0] / 10))}%`,
              }}
            >
              <span>{selectedPoint.date}</span>
              <strong>
                {privacyMode ? '••••••' : displayAmount(selectedPoint.totalAssetValue)}
              </strong>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
