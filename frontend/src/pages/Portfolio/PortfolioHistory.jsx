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
  onPeriodChange,
}) {
  const geometry = historyChartGeometry(points)
  const latest = points.at(-1) ?? null
  const first = points[0] ?? null
  const change = accountValueChangePct == null ? null : Number(accountValueChangePct)
  const tone = change == null || !Number.isFinite(change)
    ? ''
    : change >= 0 ? styles.positive : styles.negative

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
        <div className={styles.historyMetrics}>
          <span>계좌 가치 변화</span>
          <strong className={tone}>{signedPct(accountValueChangePct)}</strong>
          <small>
            {first && latest
              ? `${displayAmount(first.totalAssetValue)} → ${displayAmount(latest.totalAssetValue)}`
              : '기록이 쌓이면 변화를 표시합니다.'}
          </small>
          <em>투자 수익률 아님</em>
        </div>

        <div className={styles.chartFrame}>
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
              <path d={geometry.areaPath} fill="url(#portfolio-area)" />
              <path
                d={geometry.path}
                fill="none"
                stroke="var(--hs-scatter)"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          )}
        </div>
      </div>
    </section>
  )
}
