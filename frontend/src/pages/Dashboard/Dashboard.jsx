/**
 * Dashboard.jsx — 포트폴리오 대시보드 (/)
 *
 * 섹션 순서:
 *   1) 페이지 헤더 (새로고침·편집·종목 추가 버튼)
 *   2) Signal Command Center — 시장 HERD 배너 + Action Queue + 포트폴리오 요약
 *   3) 자산 히스토리/판단 기록 보조 패널
 *   4) 보유 종목 테이블 리스트 (편집 모드 지원)
 *   5) 빈 상태 UI
 *
 * 데이터 소스:
 *   - getPortfolio()          → 종목 목록 + avgPrice/quantity (항상 최신 호출)
 *   - getPortfolioSummary()   → DB 기준 포트폴리오 요약 (캐시 선표시 후 재검증)
 *   - getPortfolioRealtime()  → 새로고침 시 yfinance 현재가 기반 평가
 *   - getHerdObservations()   → 보유 종목 State S1 (캐시 우선)
 *   - getHerdObservation('SPY') → 시장 군중 State S1 (캐시 우선)
 *
 * 캐시 정책:
 *   최초 진입 → 사용자별 localStorage 가격 캐시를 먼저 표시하고 DB 최신값 재검증
 *             → HERD 점수는 30분 캐시 사용
 *   새로고침 버튼 → API 강제 호출 → 결과 캐시 저장
 */

import { useNavigate } from 'react-router-dom'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import styles        from './Dashboard.module.css'
import DashboardHoldings from './DashboardHoldings'
import DashboardMobile from './DashboardMobile'
import DashboardAssetHistory from './DashboardAssetHistory'
import DashboardCommandCenter from './DashboardCommandCenter'
import DashboardDataStatus from './DashboardDataStatus'
import DashboardHeader from './DashboardHeader'
import DashboardPortfolioEditor from './DashboardPortfolioEditor'
import DashboardTodayBrief from './DashboardTodayBrief'
import DashboardSupportingDetails from './DashboardSupportingDetails'
import { useDashboardData } from './useDashboardData'


/* ── 컴포넌트 ─────────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate()
  const {
    portfolio, summary, herdMap, spyData, dataStatus, dataStatusError,
    spyHistory,
    spyHistoryPeriod, setSpyHistoryPeriod, spyHistoryLoading,
    spyTab, setSpyTab, loading, error,
    modalTicker, setModalTicker, deletingTicker,
    exchangeRate, refreshing, refreshNotice, lastUpdated,
    currencyMode, editMode, setEditMode,
    portfolioSort, targetWeights,
    cashBalance, cashDraft, setCashDraft, cashSaving,
    assetPanelOpen, setAssetPanelOpen,
    assetHistoryPeriod, setAssetHistoryPeriod,
    assetHistoryLoading, assetHistoryError,
    today, fetchData, priceMap,
    handleCurrencyToggle, displayAmount, displayPnl,
    handleRefresh, handleCashSave, handleDelete,
    handlePortfolioSortChange,
    spyScore, spyStage, d1AvgPoint, m1AvgPoint, y1AvgPoint,
    spyMomentum, signalJournalSummary, recentSignalLogs,
    handleModalSaved, modalStock, rows, sortedPortfolio,
    riskWarnings, portfolioAlerts, actionQueueCards,
    assetChartHistory, assetLatest, assetFirst, assetStartValue,
    totalFlowPct, investedChangePct, assetDrawdownPct,
    assetYDomain, assetPeriodLabel, assetStartLabel,
    handleTargetWeightChange,
  } = useDashboardData()
  return (
    <div className={styles.dashboardShell}>

      <DashboardHeader
        today={today}
        lastUpdated={lastUpdated}
        marketDataDate={summary?.market_data_date}
        refreshNotice={refreshNotice}
        refreshing={refreshing}
        loading={loading}
        editMode={editMode}
        onRefresh={handleRefresh}
        onToggleEdit={() => setEditMode((mode) => !mode)}
        onAddStock={() => navigate('/search')}
      />

      <DashboardDataStatus status={dataStatus} failed={dataStatusError} />

      <DashboardMobile
        spyData={spyData}
        spyScore={spyScore}
        spyStage={spyStage}
        spyMomentum={spyMomentum}
        lastUpdated={lastUpdated}
        d1AvgPoint={d1AvgPoint}
        m1AvgPoint={m1AvgPoint}
        y1AvgPoint={y1AvgPoint}
        loading={loading}
        error={error}
        portfolio={portfolio}
        actionQueueCards={actionQueueCards}
        summary={summary}
        displayAmount={displayAmount}
        cashBalance={cashBalance}
        currencyMode={currencyMode}
        assetPanelOpen={assetPanelOpen}
        onCurrencyToggle={handleCurrencyToggle}
        onToggleAssetPanel={() => setAssetPanelOpen((open) => !open)}
        onNavigate={navigate}
      />

      {!loading && !error && portfolio.length > 0 && (
        <DashboardTodayBrief
          cards={actionQueueCards}
          alerts={portfolioAlerts}
          summary={summary}
          displayAmount={displayAmount}
          onOpenStock={(ticker) => navigate(`/stock/${ticker}`)}
        />
      )}

      <DashboardCommandCenter
        spyData={spyData}
        spyScore={spyScore}
        spyStage={spyStage}
        spyMomentum={spyMomentum}
        spyTab={spyTab}
        onSpyTabChange={setSpyTab}
        d1AvgPoint={d1AvgPoint}
        m1AvgPoint={m1AvgPoint}
        y1AvgPoint={y1AvgPoint}
        lastUpdated={lastUpdated}
        marketDataDate={summary?.market_data_date}
        spyHistoryPeriod={spyHistoryPeriod}
        onSpyHistoryPeriodChange={setSpyHistoryPeriod}
        spyHistoryLoading={spyHistoryLoading}
        spyHistory={spyHistory}
        summary={summary}
        displayAmount={displayAmount}
        displayPnl={displayPnl}
        cashBalance={cashBalance}
        currencyMode={currencyMode}
        onCurrencyToggle={handleCurrencyToggle}
        assetPanelOpen={assetPanelOpen}
        onToggleAssetPanel={() => setAssetPanelOpen((open) => !open)}
        onOpenModelReport={() => navigate('/herd-lab')}
      />

      {/* ── 로딩 ── */}
      {loading && (
        <div className={styles.loadingState}>
          <span className={styles.loadingText}>로딩 중…</span>
        </div>
      )}

      {/* ── 에러 ── */}
      {!loading && error && (
        <div className={styles.errorState}>
          <p className={styles.errorText}>{error}</p>
          <button className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
        </div>
      )}

      {/* ── 포트폴리오 세부 패널 ── */}
      {summary && (
        <>
          {editMode && (
            <DashboardPortfolioEditor
              cashDraft={cashDraft}
              cashSaving={cashSaving}
              onCashDraftChange={setCashDraft}
              onCashSave={handleCashSave}
            />
          )}

          {assetPanelOpen && (
            <DashboardAssetHistory
              summary={summary}
              cashBalance={cashBalance}
              history={assetChartHistory}
              latest={assetLatest}
              first={assetFirst}
              startValue={assetStartValue}
              totalFlowPct={totalFlowPct}
              investedChangePct={investedChangePct}
              drawdownPct={assetDrawdownPct}
              yDomain={assetYDomain}
              period={assetHistoryPeriod}
              periodLabel={assetPeriodLabel}
              startLabel={assetStartLabel}
              loading={assetHistoryLoading}
              error={assetHistoryError}
              displayAmount={displayAmount}
              onPeriodChange={setAssetHistoryPeriod}
            />
          )}

          {exchangeRate != null && (
            <div className={styles.exchangeRateRow}>
              <span className={styles.exchangeRateText}>
                {`USD/KRW ${Number(exchangeRate).toLocaleString('ko-KR', {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })} · 15분 지연`}
              </span>
            </div>
          )}

          <DashboardSupportingDetails
            riskWarnings={riskWarnings}
            alerts={portfolioAlerts}
            journalSummary={signalJournalSummary}
            recentLogs={recentSignalLogs}
            onOpenStock={(ticker) => navigate(`/stock/${ticker}`)}
            onOpenJournal={() => navigate('/journal')}
          />
        </>
      )}

      {/* ── 보유 종목 ── */}
      {!loading && !error && (
        <DashboardHoldings
          portfolio={portfolio}
          sortedPortfolio={sortedPortfolio}
          rows={rows}
          herdMap={herdMap}
          priceMap={priceMap}
          portfolioSort={portfolioSort}
          editMode={editMode}
          deletingTicker={deletingTicker}
          targetWeights={targetWeights}
          displayAmount={displayAmount}
          displayPnl={displayPnl}
          onSortChange={handlePortfolioSortChange}
          onDelete={handleDelete}
          onOpenStock={(ticker) => navigate(`/stock/${ticker}`)}
          onEditHolding={setModalTicker}
          onTargetWeightChange={handleTargetWeightChange}
        />
      )}

      {/* ── 빈 상태 ── */}
      {!loading && !error && portfolio.length === 0 && (
        <div className={styles.emptyState}>
          <p className={styles.emptyTitle}>아직 종목이 없습니다.</p>
          <p className={styles.emptyDesc}>종목을 추가해보세요.</p>
          <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
            종목 추가
          </button>
        </div>
      )}

      {/* ── 평단가 입력/수정 모달 ── */}
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
