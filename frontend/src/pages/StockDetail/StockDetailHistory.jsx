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
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <div className={styles.cardTitle}>HERD State S1 History</div>
          <div className={styles.cardMeta}>주간 관찰 · 1M · 3M · 1Y · 3Y</div>
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
      <div className={styles.cardBody}>
        {loading ? (
          <div className={styles.chartEmpty}>로딩 중…</div>
        ) : (
          <HerdHistoryChart points={points} currentScore={currentScore} height={230} />
        )}
      </div>
    </div>
  )
}
