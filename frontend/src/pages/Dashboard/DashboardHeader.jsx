import styles from './Dashboard.module.css'
import { REFRESH_SCOPE_TITLE, fmtAxisDate, fmtTime } from './dashboardModel'

export default function DashboardHeader({
  today,
  lastUpdated,
  marketDataDate,
  refreshNotice,
  refreshing,
  loading,
  editMode,
  onRefresh,
  onToggleEdit,
  onAddStock,
}) {
  return (
    <div className={styles.pageHeader}>
      <div>
        <div className={styles.pageDate}>{today}</div>
        <h1 className={styles.pageTitle}>내 포트폴리오</h1>
        <p className={styles.pageSubtitle}>시장 흐름과 보유 종목의 행동 대기열을 먼저 확인합니다.</p>
      </div>
      <div className={styles.headerActions}>
        {lastUpdated && (
          <span className={styles.updateTime}>
            {marketDataDate && `종가 ${fmtAxisDate(marketDataDate)} · `}
            업데이트 · {fmtTime(lastUpdated)}
          </span>
        )}
        {refreshNotice && <span className={styles.refreshNotice}>{refreshNotice}</span>}
        <button
          className={styles.btnRefresh}
          onClick={onRefresh}
          disabled={refreshing || loading}
          title={REFRESH_SCOPE_TITLE}
        >
          {refreshing ? '새로고침 중…' : '↻ 새로고침'}
        </button>
        <button
          className={`${styles.btnEdit} ${editMode ? styles.btnEditActive : ''}`}
          onClick={onToggleEdit}
        >
          {editMode ? '완료' : '편집'}
        </button>
        <button className={styles.btnPrimary} onClick={onAddStock}>종목 추가</button>
      </div>
    </div>
  )
}
