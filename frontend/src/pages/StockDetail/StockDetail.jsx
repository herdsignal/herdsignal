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
import StockDetailBrief from './StockDetailBrief'
import StockDetailRecords from './StockDetailRecords'
import StockOperatingReview from './StockOperatingReview'
import { BTN_LABELS, badgeColors } from './stockDetailModel'
import { useStockDetail } from './useStockDetail'

export default function StockDetail() {
  const { ticker } = useParams()
  const navigate = useNavigate()
  const detail = useStockDetail(ticker)
  const {
    observation,
    authenticated,
    observationAvailable,
    loading,
    error,
    portfolioStatus,
    watchlistStatus,
    historyPeriod,
    setHistoryPeriod,
    historyLoading,
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
    dailyObservation,
    dailyObservationAvailable,
    displayHerdScore,
    displayHerdStage,
    stageDisp,
    color,
    fundamentalGuard,
    journalSummary,
    historyPoints,
    timelineMeta,
    episodeStudy,
    episodeLoading,
    historicalContext,
    historicalContextLoading,
    briefItems,
    stateSummary,
    handleJournalAction,
    handleJournalDelete,
    operatingReview,
  } = detail
  const records = (
    <StockDetailRecords
      authenticated={authenticated}
      financialsLoading={financialsLoading}
      financials={financials}
      fundamentalGuard={fundamentalGuard}
      journalSummary={journalSummary}
      signalLogs={signalLogs}
      onCreateJournal={setJournalAction}
      onDeleteJournal={handleJournalDelete}
    />
  )

  return (
    <div className={styles.page} aria-busy={loading}>
      <nav className={styles.breadcrumb} aria-label="현재 위치">
        <button type="button" className={styles.breadcrumbLink} onClick={() => navigate('/app#stock-search')}>
          종목
        </button>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{normalizedTicker}</span>
      </nav>

      <div className={styles.stockHeader}>
        <div className={styles.stockHeaderLeft}>
          <StockAvatar
            ticker={normalizedTicker}
            logoUrl={observation?.logoUrl}
            size="lg"
            tone={observationAvailable ? badgeColors(herdStage) : undefined}
          />
          <div>
            <div className={styles.stockTicker}>{normalizedTicker}</div>
            <div className={styles.stockFullname}>
              {[observation?.companyName, observation?.sector].filter(Boolean).join(' · ') || '미국 주식'}
            </div>
          </div>
        </div>
        <div className={styles.stockHeaderRight}>
          {!authenticated && (
            <button type="button" className={styles.btnPrimary} onClick={() => navigate('/login')}>
              로그인
            </button>
          )}
          {authenticated && (
            <>
          <button
            type="button"
            className={styles.btnWatchlist}
            onClick={handleAddWatchlist}
            disabled={watchlistStatus === 'loading'}
          >
            {BTN_LABELS.watchlist[watchlistStatus]}
          </button>
          <button
            type="button"
            className={styles.btnPrimary}
            onClick={handleAddPortfolio}
            disabled={portfolioStatus === 'loading'}
          >
            {BTN_LABELS.portfolio[portfolioStatus]}
          </button>
            </>
          )}
        </div>
      </div>

      {actionError && (
        <div className={styles.actionError} role="alert">{actionError}</div>
      )}
      {loading && (
        <div className={styles.loadingState} role="status">
          <span className={styles.loadingText}>로딩 중…</span>
        </div>
      )}
      {!loading && error && (
        <div className={styles.errorState} role="alert">
          {error.split('\n').map((line, index) => (
            <p key={`${index}-${line}`} className={index === 0 ? styles.errorTitle : styles.errorSub}>
              {line}
            </p>
          ))}
          <button type="button" className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
        </div>
      )}

      {!loading && !error && !observationAvailable && (
        <div className={styles.errorState} role="status">
          <p className={styles.errorTitle}>HERD 관찰값 준비 중</p>
          <p className={styles.errorSub}>
            이전 모델 점수로 대체 표시하지 않습니다. 다음 주간 갱신 후 다시 확인해주세요.
          </p>
          <button type="button" className={styles.retryBtn} onClick={fetchData}>다시 확인</button>
        </div>
      )}

      {!loading && !observationAvailable && (
        <div className={styles.contentGrid}>
          <div className={styles.colMain}>
            <nav className={styles.detailNav} aria-label="종목 상세 구역">
              <a href="#stock-records">기업 정보</a>
              {authenticated && <a href="#stock-journal">판단 기록</a>}
            </nav>
            {records}
          </div>
        </div>
      )}

      {!loading && !error && observationAvailable && (
        <div className={styles.contentGrid}>
          <div className={styles.colMain}>
            <nav className={styles.detailNav} aria-label="종목 상세 구역">
              <a href="#stock-state">현재 상태</a>
              <a href="#stock-history">가격 · HERD 이력</a>
              <a href="#stock-evidence">HERD 근거</a>
              <a href="#stock-operating-review">장기 운용 검토</a>
              <a href="#stock-records">기업 정보</a>
              {authenticated && <a href="#stock-journal">판단 기록</a>}
            </nav>
            <StockDetailHero
              herdScore={herdScore}
              herdStage={herdStage}
              displayHerdScore={displayHerdScore}
              displayHerdStage={displayHerdStage}
              dailyObservation={dailyObservation}
              dailyObservationAvailable={dailyObservationAvailable}
              stateSummary={stateSummary}
            />
            <StockDetailBrief items={briefItems} />
            <StockDetailHistory
              period={historyPeriod}
              onPeriodChange={setHistoryPeriod}
              loading={historyLoading}
              points={historyPoints}
              currentScore={herdScore}
              episodeStudy={episodeStudy}
              episodeLoading={episodeLoading}
              historicalContext={historicalContext}
              historicalContextLoading={historicalContextLoading}
              timelineMeta={timelineMeta}
              observation={observation}
            />
            <StockDetailAnalysis
              observation={observation}
              color={color}
            />
            <StockOperatingReview state={operatingReview} />
            {records}
          </div>
        </div>
      )}

      {authenticated && journalAction && observationAvailable && (
        <SignalJournalModal
          ticker={normalizedTicker}
          actionType={journalAction}
          herdSnapshot={{
            score: Math.round(herdScore),
            stage: stageDisp,
            signalLabel: 'HERD 관찰',
          }}
          onClose={() => setJournalAction(null)}
          onSave={(details) => handleJournalAction(journalAction, details)}
        />
      )}
    </div>
  )
}
