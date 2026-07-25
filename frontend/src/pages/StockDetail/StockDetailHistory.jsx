import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import styles from './StockDetail.module.css'
import { HISTORY_PERIODS } from './stockDetailModel'

export default function StockDetailHistory({
  period,
  onPeriodChange,
  loading,
  points,
  currentScore,
}) {
  return (
    <section className={styles.historySection} aria-labelledby="stock-history-title">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="stock-history-title">HERD 이력</h2>
          <span>주간 관찰</span>
        </div>
        <div className={styles.historyTabs}>
          {HISTORY_PERIODS.map((item) => (
            <button
              key={item.value}
              className={`${styles.historyTab} ${period === item.value ? styles.historyTabActive : ''}`}
              onClick={() => onPeriodChange(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className={styles.historyBody}>
        {loading ? (
          <div className={styles.chartEmpty}>로딩 중…</div>
        ) : (
          <HerdHistoryChart points={points} currentScore={currentScore} height={230} />
        )}
      </div>
    </section>
  )
}
