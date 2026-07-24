import styles from './Dashboard.module.css'

export default function DashboardPortfolioEditor({
  cashDraft,
  cashSaving,
  onCashDraftChange,
  onCashSave,
}) {
  return (
    <div className={styles.portfolioEditPanel}>
      <div className={styles.portfolioEditInfo}>
        <span>포트폴리오 설정</span>
        <strong>현금 보유액</strong>
        <em>총자산과 목표 비중 계산에 함께 반영됩니다.</em>
      </div>
      <div className={styles.cashEditControl}>
        <div className={styles.cashInputRow}>
          <span className={styles.cashPrefix}>$</span>
          <input
            className={styles.cashInput}
            type="number"
            min="0"
            step="0.01"
            inputMode="decimal"
            value={cashDraft}
            onChange={(event) => onCashDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') onCashSave()
            }}
            placeholder="0.00"
            aria-label="현금 보유액"
          />
        </div>
        <button
          type="button"
          className={styles.cashSaveBtn}
          onClick={onCashSave}
          disabled={cashSaving}
        >
          {cashSaving ? '저장 중…' : '현금 저장'}
        </button>
      </div>
    </div>
  )
}
