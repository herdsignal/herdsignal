import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import PortfolioHistory from './PortfolioHistory'
import PortfolioHoldings from './PortfolioHoldings'
import PortfolioExposure from './PortfolioExposure'
import PortfolioHerdField from './PortfolioHerdField'
import { usePortfolioPageData } from './usePortfolioPageData'
import styles from './Portfolio.module.css'

function formatPct(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  const numeric = Number(value)
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(2)}%`
}

export default function Portfolio() {
  const navigate = useNavigate()
  const [manageOpen, setManageOpen] = useState(false)
  const {
    portfolio,
    summary,
    loading,
    error,
    refreshing,
    refreshNotice,
    lastUpdated,
    currencyMode,
    exchangeRate,
    selectCurrency,
    cashBalance,
    cashDraft,
    setCashDraft,
    cashSaving,
    assetHistoryPeriod,
    setAssetHistoryPeriod,
    assetHistoryLoading,
    assetHistoryError,
    assetChartHistory,
    assetPeriodLabel,
    accountValueChangePct,
    sortedRows,
    sortBy,
    selectSort,
    todayChange,
    exposure,
    herdField,
    displayAmount,
    displaySignedAmount,
    refresh,
    fetchData,
    handleCashSave,
    handleDelete,
    handleTargetWeightSave,
    deletingTicker,
    targetSavingTicker,
    modalTicker,
    setModalTicker,
    modalStock,
    handleModalSaved,
  } = usePortfolioPageData()
  const todayTone = Number(todayChange.pct) >= 0 ? styles.positive : styles.negative
  const totalAsset = summary?.total_asset_value ?? summary?.total_value
  const invested = summary?.invested_value

  return (
    <div className={styles.page} aria-busy={loading || refreshing}>
      <header className={styles.pageHeader}>
        <div>
          <span className={styles.eyebrow}>PORTFOLIO LENS</span>
          <h1>내 포트폴리오</h1>
        </div>
        <div className={styles.headerControls}>
          <div className={styles.currencyToggle} aria-label="표시 통화">
            {['KRW', 'USD'].map((mode) => (
              <button
                type="button"
                key={mode}
                className={currencyMode === mode ? styles.activeTab : ''}
                aria-pressed={currencyMode === mode}
                onClick={() => selectCurrency(mode)}
              >
                {mode}
              </button>
            ))}
          </div>
          <button
            type="button"
            className={styles.controlButton}
            aria-expanded={manageOpen}
            aria-controls="portfolio-manage-panel"
            onClick={() => setManageOpen((open) => !open)}
          >
            관리
          </button>
          <button
            type="button"
            className={styles.controlButton}
            disabled={loading || refreshing}
            onClick={refresh}
          >
            {refreshing ? '갱신 중…' : '새로고침'}
          </button>
        </div>
      </header>

      {refreshNotice && <p className={styles.notice} role="status">{refreshNotice}</p>}

      {manageOpen && (
        <section id="portfolio-manage-panel" className={styles.managePanel} aria-label="포트폴리오 관리">
          <label htmlFor="portfolio-cash">현금 보유액 (USD)</label>
          <div>
            <input
              id="portfolio-cash"
              type="number"
              min="0"
              step="0.01"
              value={cashDraft}
              placeholder={String(cashBalance || 0)}
              onChange={(event) => setCashDraft(event.target.value)}
            />
            <button type="button" disabled={cashSaving} onClick={handleCashSave}>
              {cashSaving ? '저장 중…' : '현금 저장'}
            </button>
            <button type="button" onClick={() => navigate('/search')}>종목 추가</button>
          </div>
        </section>
      )}

      {loading && (
        <section className={styles.statePanel} role="status">포트폴리오 불러오는 중…</section>
      )}
      {!loading && error && (
        <section className={styles.statePanel} role="alert">
          <p>{error}</p>
          <button type="button" onClick={fetchData}>다시 시도</button>
        </section>
      )}

      {!loading && !error && portfolio.length === 0 && (
        <section className={styles.emptyState}>
          <span>EMPTY PORTFOLIO</span>
          <h2>첫 종목을 기록해보세요.</h2>
          <button type="button" onClick={() => navigate('/search')}>종목 찾기</button>
        </section>
      )}

      {!loading && !error && portfolio.length > 0 && (
        <>
          <section className={styles.accountSummary} aria-label="포트폴리오 요약">
            <div className={styles.totalBlock}>
              <span>전체 자산</span>
              <strong>{displayAmount(totalAsset)}</strong>
              <p className={todayTone}>
                오늘 {displaySignedAmount(todayChange.amount)}
                <b>{formatPct(todayChange.pct)}</b>
              </p>
            </div>
            <dl className={styles.balanceBreakdown}>
              <div>
                <dt>주식 평가액</dt>
                <dd>{displayAmount(invested)}</dd>
              </div>
              <div>
                <dt>현금</dt>
                <dd>{displayAmount(cashBalance)}</dd>
              </div>
            </dl>
          </section>

          <PortfolioHistory
            points={assetChartHistory}
            period={assetHistoryPeriod}
            periodLabel={assetPeriodLabel}
            accountValueChangePct={accountValueChangePct}
            loading={assetHistoryLoading}
            error={assetHistoryError}
            displayAmount={displayAmount}
            onPeriodChange={setAssetHistoryPeriod}
          />

          <PortfolioHerdField
            field={herdField}
            onOpenStock={(ticker) => navigate(`/stock/${ticker}`)}
          />

          <PortfolioExposure exposure={exposure} />

          <PortfolioHoldings
            rows={sortedRows}
            sortBy={sortBy}
            deletingTicker={deletingTicker}
            displayAmount={displayAmount}
            displaySignedAmount={displaySignedAmount}
            onSortChange={selectSort}
            onOpenStock={(ticker) => navigate(`/stock/${ticker}`)}
            onEditHolding={setModalTicker}
            onDelete={handleDelete}
            onTargetWeightSave={handleTargetWeightSave}
            targetSavingTicker={targetSavingTicker}
          />

          <footer className={styles.meta}>
            <span>
              {lastUpdated
                ? `${lastUpdated.toLocaleString('ko-KR')} 갱신`
                : '가격 갱신 시각 없음'}
            </span>
            <span>
              {currencyMode === 'KRW' && exchangeRate
                ? `USD/KRW ${exchangeRate.toLocaleString('ko-KR')}`
                : 'USD 기준 자산'}
            </span>
          </footer>
        </>
      )}

      {modalTicker && (
        <AvgPriceModal
          ticker={modalTicker}
          currentAvgPrice={modalStock?.avgPrice ?? null}
          currentQuantity={modalStock?.quantity ?? null}
          onClose={() => setModalTicker(null)}
          onSaved={handleModalSaved}
        />
      )}
    </div>
  )
}
