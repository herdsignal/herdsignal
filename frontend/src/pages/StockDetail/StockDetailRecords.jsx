import styles from './StockDetail.module.css'
import StockDetailFundamentals from './StockDetailFundamentals'
import StockDetailJournal from './StockDetailJournal'

export default function StockDetailRecords({
  financialsLoading,
  financials,
  fundamentalGuard,
  journalSummary,
  signalLogs,
  onCreateJournal,
  onDeleteJournal,
}) {
  return (
    <details className={styles.detailDisclosure}>
      <summary>
        <div><span>투자 기록</span><strong>재무 가드·나의 판단 기록</strong></div>
        <em>펼쳐보기</em>
      </summary>
      <div className={styles.detailDisclosureBody}>
        <StockDetailFundamentals
          loading={financialsLoading}
          financials={financials}
          guard={fundamentalGuard}
        />
        <StockDetailJournal
          summary={journalSummary}
          logs={signalLogs}
          onCreate={onCreateJournal}
          onDelete={onDeleteJournal}
        />
      </div>
    </details>
  )
}
