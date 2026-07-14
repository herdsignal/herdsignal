import {
  fmtCurrencyCompact,
  fmtFinancePct,
  fmtNumber,
  fundamentalTone,
} from './stockDetailModel'
import styles from './StockDetail.module.css'

export default function StockDetailFundamentals({ loading, financials, guard }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div><div className={styles.cardTitle}>재무 가드</div><div className={styles.cardMeta}>HERD 신호 보조 필터</div></div>
        {!loading && <div className={styles.fundamentalBadge} style={{ color: fundamentalTone(guard.level), borderColor: fundamentalTone(guard.level) }}>{guard.label}</div>}
      </div>
      <div className={styles.cardBodySmall}>
        {loading ? <div className={styles.chartEmpty}>로딩 중…</div> : (
          <>
            <div className={styles.fundamentalSummary}>{guard.summary}</div>
            <div className={styles.fundamentalGrid}>
              <Fundamental label="시가총액" value={fmtCurrencyCompact(financials?.marketCap)} />
              <Fundamental label="PER" value={fmtNumber(financials?.trailingPe)} />
              <Fundamental label="EPS" value={fmtNumber(financials?.eps, 2)} />
              <Fundamental label="영업이익률" value={fmtFinancePct(financials?.operatingMargin)} />
              <Fundamental label="매출" value={fmtCurrencyCompact(financials?.totalRevenue)} />
            </div>
            {guard.reasons.length > 0 && <div className={styles.fundamentalReasons}>{guard.reasons.map((reason) => <span key={reason}>{reason}</span>)}</div>}
          </>
        )}
      </div>
    </div>
  )
}

function Fundamental({ label, value }) {
  return <div className={styles.fundamentalItem}><span>{label}</span><strong>{value}</strong></div>
}
