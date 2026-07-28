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
    <section id="stock-records" className={styles.recordsSection} aria-labelledby="stock-records-title">
      <header className={styles.recordsHeader}>
        <span>CONTEXT &amp; JOURNAL</span>
        <h2 id="stock-records-title">
          {authenticated ? '기업 정보 · 판단 기록' : '기업 정보'}
        </h2>
      </header>
      <div className={styles.recordsBody}>
        <StockDetailFundamentals
          loading={financialsLoading}
          financials={financials}
          guard={fundamentalGuard}
        />
        {authenticated && (
          <div id="stock-journal">
            <StockDetailJournal
              summary={journalSummary}
              logs={signalLogs}
              onCreate={onCreateJournal}
              onDelete={onDeleteJournal}
            />
          </div>
        )}
      </div>
    </section>
  )
}
