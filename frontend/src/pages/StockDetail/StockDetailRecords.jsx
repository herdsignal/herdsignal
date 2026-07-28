import styles from './StockDetail.module.css'
import StockDetailFundamentals from './StockDetailFundamentals'
import StockDetailJournal from './StockDetailJournal'

export default function StockDetailRecords({
  authenticated = true,
  financialsLoading,
  financials,
  fundamentalGuard,
  journalSummary,
  signalLogs,
  onCreateJournal,
  onDeleteJournal,
}) {
  return (
    <section className={styles.recordsSection} aria-labelledby="stock-records-title">
      <header className={styles.recordsHeader}>
        <span>CONTEXT &amp; JOURNAL</span>
        <h2 id="stock-records-title">기업 정보 · 판단 로그</h2>
      </header>
      <div className={styles.recordsBody}>
        <StockDetailFundamentals
          loading={financialsLoading}
          financials={financials}
          guard={fundamentalGuard}
        />
        {authenticated && (
          <StockDetailJournal
            summary={journalSummary}
            logs={signalLogs}
            onCreate={onCreateJournal}
            onDelete={onDeleteJournal}
          />
        )}
      </div>
    </section>
  )
}
