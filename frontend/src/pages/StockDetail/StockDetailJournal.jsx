import {
  formatJournalAmount,
  formatJournalCount,
  formatJournalPrice,
  formatJournalProfit,
  formatJournalQuantity,
  formatJournalTime,
} from '../../utils/signalJournal'
import styles from './StockDetail.module.css'

export default function StockDetailJournal({ summary, logs, onCreate, onDelete }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div><div className={styles.cardTitle}>내 판단 기록</div><div className={styles.cardMeta}>HERD 신호를 보고 남긴 실사용 로그</div></div>
        <div className={styles.cardMeta}>{formatJournalCount(summary.totalCount)}</div>
      </div>
      <div className={styles.cardBodySmall}>
        <div className={styles.journalSummaryGrid}>
          <JournalStat label="매수 기록" count={summary.buyCount} detail={formatJournalAmount(summary.buyAmount) ?? '$0'} />
          <JournalStat label="익절 기록" count={summary.sellCount} detail={formatJournalAmount(summary.sellAmount) ?? '$0'} />
          <JournalStat label="평균 익절률" count={summary.hasProfitData ? formatJournalProfit(summary.avgProfitPct) : '—'} detail="입력 기록 기준" formatted />
        </div>
        <div className={styles.journalActions}>
          <button type="button" className={styles.journalBtn} onClick={() => onCreate('BUY')}>매수 기록</button>
          <button type="button" className={styles.journalBtn} onClick={() => onCreate('HOLD')}>보류 기록</button>
          <button type="button" className={styles.journalBtn} onClick={() => onCreate('SELL')}>익절 기록</button>
        </div>
        {logs.length > 0 ? (
          <div className={styles.journalList}>
            {logs.slice(0, 3).map((log) => (
              <div key={log.id} className={styles.journalItem}>
                <span>{formatJournalTime(log.recordedAt ?? log.createdAt)}</span>
                <strong>{log.actionLabel}</strong>
                <em>{journalDetail(log)}</em>
                {log.memo && <small>{log.memo}</small>}
                <button type="button" className={styles.journalDelete} onClick={() => onDelete(log.id)} aria-label={`${log.actionLabel} 삭제`}>삭제</button>
              </div>
            ))}
          </div>
        ) : <div className={styles.journalEmpty}>아직 기록이 없습니다.</div>}
      </div>
    </div>
  )
}

function JournalStat({ label, count, detail, formatted = false }) {
  return <div className={styles.journalSummaryItem}><span>{label}</span><strong>{formatted ? count : formatJournalCount(count)}</strong><em>{detail}</em></div>
}

function journalDetail(log) {
  return [
    formatJournalPrice(log.price), formatJournalQuantity(log.quantity),
    formatJournalAmount(log.amount), formatJournalProfit(log.profitPct),
  ].filter(Boolean).join(' · ') || `HERD ${log.herdScore} · ${log.signalLabel}`
}
