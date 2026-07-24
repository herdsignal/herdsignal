/**
 * 종목 상세 페이지. 데이터 오케스트레이션과 최상위 화면 상태만 담당한다.
 */

import { useNavigate, useParams } from 'react-router-dom'
import SignalJournalModal from '../../components/SignalJournalModal/SignalJournalModal'
import StockAvatar from '../../components/StockAvatar/StockAvatar'
import styles from './StockDetail.module.css'
import StockDetailAnalysis from './StockDetailAnalysis'
import StockDetailHero from './StockDetailHero'
import StockDetailHistory from './StockDetailHistory'
import StockDetailRecords from './StockDetailRecords'
import { BTN_LABELS, badgeColors } from './stockDetailModel'
import { useStockDetail } from './useStockDetail'

export default function StockDetail() {
  const { ticker } = useParams()
  const navigate = useNavigate()
  const detail = useStockDetail(ticker)
  const {
    herdData,
    loading,
    error,
    portfolioStatus,
    watchlistStatus,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
    reliability,
    reliabilityLoading,
    financials,
    financialsLoading,
    signalLogs,
    journalAction,
    setJournalAction,
    actionError,
    normalizedTicker,
    fetchData,
    handleAddPortfolio,
    handleAddWatchlist,
    herdScore,
    herdStage,
    stageDisp,
    color,
    sigStyle,
    qualityToneColor,
    actionColor,
    decision,
    currentReliability,
    reliabilityEvidence,
    fundamentalGuard,
    signalEvidence,
    journalSummary,
    historyPoints,
    herdMomentum,
    handleJournalAction,
    handleJournalDelete,
  } = detail

  return (
    <div>
      <div className={styles.breadcrumb}>
        <span className={styles.breadcrumbLink} onClick={() => navigate('/app')}>
          포트폴리오
        </span>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{normalizedTicker}</span>
      </div>

      <div className={styles.stockHeader}>
        <div className={styles.stockHeaderLeft}>
          <StockAvatar
            ticker={normalizedTicker}
            logoUrl={herdData?.logoUrl}
            size="lg"
            tone={herdData ? badgeColors(herdStage) : undefined}
          />
          <div>
            <div className={styles.stockTicker}>{normalizedTicker}</div>
            <div className={styles.stockFullname}>
              {[herdData?.companyName, herdData?.sector].filter(Boolean).join(' · ') || '미국 주식'}
            </div>
          </div>
        </div>
        <div className={styles.stockHeaderRight}>
          <button
            className={styles.btnWatchlist}
            onClick={handleAddWatchlist}
            disabled={watchlistStatus === 'loading'}
          >
            {BTN_LABELS.watchlist[watchlistStatus]}
          </button>
          <button
            className={styles.btnPrimary}
            onClick={handleAddPortfolio}
            disabled={portfolioStatus === 'loading'}
          >
            {BTN_LABELS.portfolio[portfolioStatus]}
          </button>
        </div>
      </div>

      {actionError && (
        <div className={styles.actionError} role="alert">{actionError}</div>
      )}
      {loading && (
        <div className={styles.loadingState}>
          <span className={styles.loadingText}>로딩 중…</span>
        </div>
      )}
      {!loading && error && (
        <div className={styles.errorState}>
          {error.split('\n').map((line, index) => (
            <p key={`${index}-${line}`} className={index === 0 ? styles.errorTitle : styles.errorSub}>
              {line}
            </p>
          ))}
          <button className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
        </div>
      )}

      {!loading && !error && herdData && (
        <div className={styles.contentGrid}>
          <div className={styles.colMain}>
            <StockDetailHero
              herdData={herdData}
              herdScore={herdScore}
              stageDisp={stageDisp}
              color={color}
              sigStyle={sigStyle}
              qualityToneColor={qualityToneColor}
              actionColor={actionColor}
              decision={decision}
              herdMomentum={herdMomentum}
            />
            <StockDetailAnalysis
              herdData={herdData}
              color={color}
              signalEvidence={signalEvidence}
              reliability={reliability}
              reliabilityLoading={reliabilityLoading}
              currentReliability={currentReliability}
              reliabilityEvidence={reliabilityEvidence}
            />
            <StockDetailHistory
              period={historyPeriod}
              onPeriodChange={setHistoryPeriod}
              loading={historyLoading}
              points={historyPoints}
              currentScore={herdScore}
            />
            <StockDetailRecords
              financialsLoading={financialsLoading}
              financials={financials}
              fundamentalGuard={fundamentalGuard}
              journalSummary={journalSummary}
              signalLogs={signalLogs}
              onCreateJournal={setJournalAction}
              onDeleteJournal={handleJournalDelete}
            />
          </div>
        </div>
      )}

      {journalAction && (
        <SignalJournalModal
          ticker={normalizedTicker}
          actionType={journalAction}
          herdSnapshot={{
            score: Math.round(herdScore),
            stage: stageDisp,
            signalLabel: herdData?.actionLabel ?? decision.title,
          }}
          onClose={() => setJournalAction(null)}
          onSave={(details) => handleJournalAction(journalAction, details)}
        />
      )}
    </div>
  )
}
