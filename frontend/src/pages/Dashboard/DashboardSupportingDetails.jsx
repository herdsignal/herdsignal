import { alertSeverityLabel } from '../../utils/alertRules'
import {
  formatJournalAmount,
  formatJournalCount,
  formatJournalProfit,
} from '../../utils/signalJournal'
import styles from './Dashboard.module.css'

export default function DashboardSupportingDetails({
  riskWarnings,
  alerts,
  journalSummary,
  recentLogs,
  onOpenStock,
  onOpenJournal,
}) {
  const hasContent = riskWarnings.length > 0 || alerts.length > 0 || journalSummary.totalCount > 0
  if (!hasContent) return null

  return (
    <details className={styles.supportingDetails}>
      <summary>
        <div><span>추가 정보</span><strong>리스크·알림·판단 기록</strong></div>
        <em>{riskWarnings.length + alerts.length}개 점검</em>
      </summary>
      <div className={styles.supportingDetailsBody}>
        {riskWarnings.length > 0 && (
          <section className={styles.riskPanel}>
            <div className={styles.riskPanelHead}>
              <span>포트폴리오 리스크</span>
              <strong>{riskWarnings[0]?.level === 'CLEAR' ? '안정' : `${riskWarnings.length}개 점검`}</strong>
            </div>
            <div className={styles.riskList}>
              {riskWarnings.map((item) => (
                <div key={`${item.title}-${item.value}`} className={`${styles.riskItem} ${styles[`riskItem_${item.level?.toLowerCase()}`] || ''}`}>
                  <span>{item.title}</span><strong>{item.value}</strong><em>{item.detail}</em>
                </div>
              ))}
            </div>
          </section>
        )}

        {alerts.length > 0 && (
          <section className={styles.alertPanel}>
            <div className={styles.alertPanelHead}><span>알림 조건</span><strong>{alerts.length}개 활성</strong></div>
            <div className={styles.alertList}>
              {alerts.slice(0, 3).map((item) => (
                <button key={item.id} type="button" className={`${styles.alertItem} ${styles[`alertItem_${item.severity?.toLowerCase()}`] || ''}`} onClick={() => item.ticker && onOpenStock(item.ticker)}>
                  <span>{alertSeverityLabel(item.severity)}</span><strong>{item.title}</strong><em>{item.value} · {item.detail}</em>
                </button>
              ))}
            </div>
          </section>
        )}

        {journalSummary.totalCount > 0 && (
          <section className={styles.journalOverview}>
            <div className={styles.journalOverviewHead}>
              <div><span>판단 기록</span><strong>{formatJournalCount(journalSummary.totalCount)}</strong></div>
              <button type="button" className={styles.journalOverviewLink} onClick={onOpenJournal}>전체 기록 보기</button>
            </div>
            <div className={styles.journalOverviewStats}>
              <div><span>매수 총액</span><strong>{formatJournalAmount(journalSummary.buyAmount) ?? '$0'}</strong><em>{formatJournalCount(journalSummary.buyCount)}</em></div>
              <div><span>익절 총액</span><strong>{formatJournalAmount(journalSummary.sellAmount) ?? '$0'}</strong><em>{formatJournalCount(journalSummary.sellCount)}</em></div>
              <div><span>평균 익절률</span><strong>{journalSummary.hasProfitData ? formatJournalProfit(journalSummary.avgProfitPct) : '—'}</strong><em>익절 기록 기준</em></div>
            </div>
            {recentLogs.length > 0 && (
              <div className={styles.journalRecentList}>
                {recentLogs.map((log) => (
                  <button key={log.id} type="button" className={styles.journalRecentItem} onClick={() => onOpenStock(log.ticker)}>
                    <strong>{log.ticker}</strong><span>{log.actionLabel ?? log.actionType ?? '기록'}</span><em>{formatJournalAmount(log.amount) ?? `HERD ${log.herdScore ?? '—'}`}</em>
                  </button>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </details>
  )
}
