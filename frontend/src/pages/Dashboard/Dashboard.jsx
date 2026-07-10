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
 *   - getPortfolioSummary()   → DB 기준 포트폴리오 요약 (캐시 우선)
 *   - getPortfolioRealtime()  → 새로고침 시 yfinance 현재가 기반 평가
 *   - getPortfolioHerd()      → HERD 점수 (캐시 우선)
 *   - getStockHerd('SPY')     → SPY 배너용 HERD (캐시 우선)
 *
 * 캐시 정책:
 *   최초 진입 → localStorage 캐시 있으면 즉시 표시 (realtime/herd API 호출 없음)
 *             → 캐시 없으면 API 호출 후 캐시 저장
 *   새로고침 버튼 → API 강제 호출 → 결과 캐시 저장
 */

import { useNavigate } from 'react-router-dom'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { alertSeverityLabel } from '../../utils/alertRules'
import { qualityColor, qualityReasonText, qualityWarningText, shouldShowQuality } from '../../utils/dataQuality'
import { formatSignalAgeLabel } from '../../utils/signalDuration'
import {
  formatJournalAmount,
  formatJournalCount,
  formatJournalProfit,
} from '../../utils/signalJournal'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import HerdDots      from '../../components/HerdDots/HerdDots'
import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import SpectrumBar   from '../../components/SpectrumBar/SpectrumBar'
import StockAvatar   from '../../components/StockAvatar/StockAvatar'
import styles        from './Dashboard.module.css'
import { useDashboardData } from './useDashboardData'

import {
  HISTORY_PERIODS,
  ASSET_HISTORY_PERIODS,
  PORTFOLIO_SORT_OPTIONS,
  REFRESH_SCOPE_TITLE,
  stageColor,
  stageDesc,
  signalStyle,
  badgeStyle,
  buildPositionAction,
  fmtPct,
  fmtShares,
  fmtWeightGap,
  pctColor,
  fmtTime,
  fmtAxisDate,
  fmtScoreDate,
  scoreToColor,
  scoreToStage,
} from './dashboardModel'
function AssetHistoryTooltip({ active, payload, label, displayAmount }) {
  if (!active || !payload?.length) return null
  const date = new Date(label)
  const dateText = Number.isNaN(date.getTime())
    ? label
    : date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
  const row = payload[0]?.payload

  return (
    <div className={styles.assetTooltip}>
      <div className={styles.assetTooltipDate}>{dateText}</div>
      <div className={styles.assetTooltipRow}>
        <span>총자산</span>
        <strong>{displayAmount(row?.totalAssetValue)}</strong>
      </div>
      <div className={styles.assetTooltipRow}>
        <span>주식 평가액</span>
        <strong>{displayAmount(row?.investedValue)}</strong>
      </div>
      <div className={styles.assetTooltipRow}>
        <span>현금</span>
        <strong>{displayAmount(row?.cashBalance)}</strong>
      </div>
    </div>
  )
}

/**
 * SPY scoreDate 스마트 포맷 (KST 기준).
 * - 오늘: "오늘 HH:MM"  (fetchTime이 있으면 그 시각, 없으면 현재 시각)
 * - 어제: "어제"
 * - 그 이전: "MM월 DD일"
 */
function BannerStat({ label, point }) {
  const stage = scoreToStage(point?.score)

  return (
    <div className={styles.bannerStatItem}>
      <div className={styles.bannerStatLabel}>{label}</div>
      {point && stage ? (
        <>
          <div className={styles.bannerStatMain}>
            <span className={styles.bannerStatValue} style={{ color: scoreToColor(point.score) }}>
              {Math.round(point.score)}
            </span>
            <span className={styles.bannerStatStage}>{stage}</span>
          </div>
          <div className={styles.bannerStatDesc}>{stageDesc(stage)}</div>
        </>
      ) : (
        <div className={styles.bannerStatValue}>—</div>
      )}
    </div>
  )
}

/* ── 컴포넌트 ─────────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate()
  const {
    portfolio, summary, herdMap, spyData,
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
    assetChartHistory, assetLatest, assetFirst,
    totalFlowPct, investedChangePct, assetDrawdownPct,
    assetYDomain, assetPeriodLabel, assetStartLabel,
    handleTargetWeightChange,
  } = useDashboardData()
  return (
    <div className={styles.dashboardShell}>

      {/* ── 페이지 헤더 ── */}
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>내 포트폴리오</h1>
          <p className={styles.pageSubtitle}>시장 흐름과 보유 종목의 행동 대기열을 먼저 확인합니다.</p>
        </div>
        <div className={styles.headerActions}>
          {/* 마지막 캐시 저장 시각 — localStorage 'hs_cache_time' 기준 */}
          {lastUpdated && (
            <span className={styles.updateTime}>
              업데이트 · {fmtTime(lastUpdated)}
            </span>
          )}
          {refreshNotice && (
            <span className={styles.refreshNotice}>
              {refreshNotice}
            </span>
          )}
          <button
            className={styles.btnRefresh}
            onClick={handleRefresh}
            disabled={refreshing || loading}
            title={REFRESH_SCOPE_TITLE}
          >
            {refreshing ? '새로고침 중…' : '↻ 새로고침'}
          </button>
          <button
            className={`${styles.btnEdit} ${editMode ? styles.btnEditActive : ''}`}
            onClick={() => setEditMode(m => !m)}
          >
            {editMode ? '완료' : '편집'}
          </button>
          <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
            종목 추가
          </button>
        </div>
      </div>


      <section className={styles.mobileDashboard} aria-label="모바일 대시보드">
        <article className={styles.mobileSignalCard}>
          <div className={styles.mobileSignalTop}>
            <div>
              <span className={styles.mobileKicker}>Market Signal</span>
              <strong className={styles.mobileSignalTitle}>S&amp;P 500 HERD</strong>
            </div>
            <div className={styles.mobileSignalUpdate}>
              {spyData ? fmtScoreDate(spyData.scoreDate, lastUpdated) : '대기'}
            </div>
          </div>

          <div className={styles.mobileSignalMain}>
            <div className={styles.mobileSignalScore}>
              <strong style={{ color: stageColor(spyStage) }}>
                {spyData ? Math.round(spyScore) : '—'}
              </strong>
              <span style={{ color: stageColor(spyStage) }}>
                {spyStage.startsWith('Herd ') ? spyStage : `Herd ${spyStage}`}
              </span>
              <em>{stageDesc(spyStage)}</em>
            </div>
            <div className={styles.mobileSignalFlow}>
              <HerdDots score={spyScore} fill dotCount={52} />
              <div className={styles.mobileSpectrum}>
                <SpectrumBar score={spyScore} height={3} />
              </div>
            </div>
          </div>

          <div className={styles.mobileSignalStats}>
            <div>
              <span>1일 평균</span>
              <strong style={{ color: scoreToColor(d1AvgPoint?.score) }}>
                {d1AvgPoint?.score != null ? Math.round(d1AvgPoint.score) : '—'}
              </strong>
              <em>{scoreToStage(d1AvgPoint?.score) ?? '—'}</em>
            </div>
            <div>
              <span>1달 평균</span>
              <strong style={{ color: scoreToColor(m1AvgPoint?.score) }}>
                {m1AvgPoint?.score != null ? Math.round(m1AvgPoint.score) : '—'}
              </strong>
              <em>{scoreToStage(m1AvgPoint?.score) ?? '—'}</em>
            </div>
            <div>
              <span>1년 평균</span>
              <strong style={{ color: scoreToColor(y1AvgPoint?.score) }}>
                {y1AvgPoint?.score != null ? Math.round(y1AvgPoint.score) : '—'}
              </strong>
              <em>{scoreToStage(y1AvgPoint?.score) ?? '—'}</em>
            </div>
          </div>
        </article>

        {!loading && !error && portfolio.length > 0 && (
          <article className={styles.mobileActionPanel}>
            <div className={styles.mobileSectionHead}>
              <div>
                <span className={styles.mobileKicker}>Action Queue</span>
                <strong>
                  {actionQueueCards.length > 0
                    ? `${actionQueueCards.length}개 관찰 후보`
                    : '강한 행동 신호 없음'}
                </strong>
              </div>
              <button type="button" onClick={() => navigate('/watchlist')}>
                대기열
              </button>
            </div>

            <div className={styles.mobileActionList}>
              {actionQueueCards.length > 0 ? (
                actionQueueCards.map((card) => {
                  const actionColor = card.action.muted
                    ? 'var(--calm)'
                    : signalStyle(card.herd.signal).color
                  const actionTone = card.action.code.startsWith('SELL') || card.action.code.startsWith('REDUCE')
                    ? styles.mobileActionSell
                    : card.action.code.startsWith('ADD') || card.action.code.startsWith('BUY')
                      ? styles.mobileActionBuy
                      : styles.mobileActionHold

                  return (
                    <button
                      key={card.ticker}
                      type="button"
                      className={`${styles.mobileActionItem} ${actionTone}`}
                      onClick={() => navigate(`/stock/${card.ticker}`)}
                    >
                      <div className={styles.mobileActionCode} style={{ color: actionColor }}>
                        {card.action.code}
                      </div>
                      <div className={styles.mobileActionBody}>
                        <strong>{card.ticker}</strong>
                        <span>{card.stage} · HERD {card.score}</span>
                        <em>{card.action.text}</em>
                      </div>
                      <div className={styles.mobileActionMeta}>
                        <span>{card.row.currentWeight.toFixed(1)}%</span>
                        <em>목표 {card.row.targetWeight.toFixed(1)}%</em>
                      </div>
                    </button>
                  )
                })
              ) : (
                <div className={styles.mobileActionEmpty}>
                  장기투자 지표라 매일 행동 신호가 나오지 않는 것이 정상입니다.
                </div>
              )}
            </div>
          </article>
        )}

        {summary && (
          <article className={styles.mobileAssetSummary}>
            <div className={styles.mobileAssetTop}>
              <div>
                <span className={styles.mobileKicker}>Portfolio</span>
                <strong>{displayAmount(summary.total_value)}</strong>
                <em style={{ color: pctColor(summary.total_return_pct) }}>
                  {fmtPct(summary.total_return_pct)}
                </em>
              </div>
              <div className={styles.currencyToggle}>
                <button
                  className={`${styles.currencyBtn} ${currencyMode === 'KRW' ? styles.currencyBtnActive : ''}`}
                  onClick={() => handleCurrencyToggle('KRW')}
                >
                  ₩
                </button>
                <button
                  className={`${styles.currencyBtn} ${currencyMode === 'USD' ? styles.currencyBtnActive : ''}`}
                  onClick={() => handleCurrencyToggle('USD')}
                >
                  $
                </button>
              </div>
            </div>
            <div className={styles.mobileAssetGrid}>
              <div>
                <span>주식</span>
                <strong>{displayAmount(summary.invested_value ?? summary.total_value)}</strong>
              </div>
              <div>
                <span>현금</span>
                <strong>{displayAmount(summary.cash_balance ?? cashBalance)}</strong>
              </div>
              <div>
                <span>오늘</span>
                <strong style={{ color: pctColor(summary.daily_change_pct) }}>
                  {fmtPct(summary.daily_change_pct)}
                </strong>
              </div>
            </div>
            <button
              type="button"
              className={styles.mobileAssetButton}
              onClick={() => setAssetPanelOpen(open => !open)}
            >
              {assetPanelOpen ? '자산 히스토리 닫기' : '자산 히스토리 보기'}
            </button>
          </article>
        )}
      </section>

      <div className={styles.commandFrame}>
        <div className={styles.commandFrameTop}>
          <div>
            <span>Signal Command Center</span>
            <strong>현재 시장 신호</strong>
            <em>S&amp;P 500 흐름과 보유 종목 행동 대기열을 함께 확인합니다.</em>
          </div>
          <div className={styles.commandFrameMeta}>
            <span>{lastUpdated ? `업데이트 · ${fmtTime(lastUpdated)}` : '업데이트 대기'}</span>
            <button type="button" onClick={() => navigate('/herd-lab')}>
              모델 리포트
            </button>
          </div>
        </div>

        {/* ── S&P500 HERD 시장 무대 ── */}
        <div className={styles.marketBanner}>
          {/* 좌: 점수·단계 블록 */}
          <div className={styles.bannerScoreBlock}>
            <div className={styles.bannerEyebrow}>S&amp;P 500 HERD Index</div>
            <div className={styles.bannerScore} style={{ color: stageColor(spyStage) }}>
              {spyData ? Math.round(spyScore) : '—'}
            </div>
            <div className={styles.bannerStage} style={{ color: stageColor(spyStage) }}>
              {spyStage.startsWith('Herd ') ? spyStage : `Herd ${spyStage}`}
            </div>
            <div className={styles.bannerDesc}>{stageDesc(spyStage)}</div>
          </div>

          {/* 우: 탭 + 컨텐츠 */}
          <div className={styles.bannerRight}>
            {/* 탭 버튼 */}
            <div className={styles.bannerTabs}>
              <button
                className={`${styles.bannerTab} ${spyTab === 'overview' ? styles.bannerTabActive : ''}`}
                onClick={() => setSpyTab('overview')}
              >Overview</button>
              <button
                className={`${styles.bannerTab} ${spyTab === 'timeline' ? styles.bannerTabActive : ''}`}
                onClick={() => setSpyTab('timeline')}
              >Timeline</button>
            </div>

            {/* Overview 탭 */}
            {spyTab === 'overview' && (
              <div className={styles.bannerOverview}>
                <div className={styles.bannerAnimBlock}>
                  <HerdDots score={spyScore} fill dotCount={84} />
                  <div className={styles.bannerAnimLabel}>
                    <span>← Flee · 군중 이탈</span>
                    <span>Rush · 군중 밀집 →</span>
                  </div>
                  <div className={styles.bannerSpectrumOverlay}>
                    <SpectrumBar score={spyScore} height={3} />
                  </div>
                </div>
                <div className={styles.bannerHistStats}>
                  <BannerStat label="1일 평균" point={d1AvgPoint} />
                  <BannerStat label="1달 평균" point={m1AvgPoint} />
                  <BannerStat label="1년 평균" point={y1AvgPoint} />
                  <div className={styles.bannerStatItem}>
                    <div className={styles.bannerStatLabel}>강도 변화</div>
                    <div className={`${styles.bannerStatMomentum} ${styles[`momentum_${spyMomentum.tone}`] || ''}`}>
                      {spyMomentum.label}
                    </div>
                    <div className={styles.bannerStatDesc}>{spyMomentum.detail}</div>
                  </div>
                  <div className={styles.bannerStatItem}>
                    <div className={styles.bannerStatLabel}>업데이트</div>
                    <div className={styles.bannerStatUpdate}>
                      {spyData ? fmtScoreDate(spyData.scoreDate, lastUpdated) : '—'}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Timeline 탭 */}
            {spyTab === 'timeline' && (
              <div className={styles.bannerTimeline}>
                <div className={styles.bannerPeriodTabs}>
                  {HISTORY_PERIODS.map((p) => (
                    <button
                      key={p.value}
                      className={`${styles.bannerPeriodTab} ${spyHistoryPeriod === p.value ? styles.bannerPeriodTabActive : ''}`}
                      onClick={() => setSpyHistoryPeriod(p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                {spyHistoryLoading ? (
                  <div className={styles.bannerTimelineEmpty}>로딩 중…</div>
                ) : spyHistory.length === 0 ? (
                  <div className={styles.bannerTimelineEmpty}>데이터 없음</div>
                ) : (
                  <HerdHistoryChart
                    points={spyHistory}
                    currentScore={spyScore}
                    height={190}
                  />
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── 행동 대기열 — 장기투자 관찰 후보를 먼저 보여준다 ── */}
        {!loading && !error && portfolio.length > 0 && (
          <div className={styles.commandQueue}>
            <div className={styles.commandQueueHead}>
              <span>Action Queue</span>
              <strong>
                {actionQueueCards.length > 0
                  ? `${actionQueueCards.length}개 핵심 후보`
                  : '강한 행동 신호 없음'}
              </strong>
              <em>매수권·익절권·목표비중 이탈을 우선 정렬</em>
            </div>
            <div className={styles.commandQueueList}>
              {actionQueueCards.length > 0 ? (
                actionQueueCards.map((card) => {
                  const actionColor = card.action.muted
                    ? 'var(--calm)'
                    : signalStyle(card.herd.signal).color
                  const cardTone = card.action.code.startsWith('SELL') || card.action.code.startsWith('REDUCE')
                    ? styles.commandTicketSell
                    : card.action.code.startsWith('ADD') || card.action.code.startsWith('BUY')
                      ? styles.commandTicketBuy
                      : styles.commandTicketHold

                  return (
                  <button
                    key={card.ticker}
                    type="button"
                    className={`${styles.commandTicket} ${cardTone}`}
                    onClick={() => navigate(`/stock/${card.ticker}`)}
                  >
                    <span className={styles.commandActionIcon} style={{ color: actionColor }}>
                      {card.action.code.startsWith('SELL') || card.action.code.startsWith('REDUCE') ? '↓' : card.action.code.startsWith('HOLD') || card.action.code.startsWith('WAIT') ? '○' : '↑'}
                    </span>
                    <div className={styles.commandTicketMain}>
                      <strong style={{ color: actionColor }}>{card.action.code}</strong>
                      <span>{card.ticker}</span>
                      <em>{card.stage} · HERD {card.score}</em>
                    </div>
                    <div className={styles.commandTicketMeta}>
                      <span>{card.action.text}</span>
                      <small>{card.row.currentWeight.toFixed(1)}% / {card.row.targetWeight.toFixed(1)}%</small>
                      {card.price && (
                        <small style={{ color: pctColor(card.price.daily_change_pct) }}>
                          오늘 {fmtPct(card.price.daily_change_pct)}
                        </small>
                      )}
                    </div>
                  </button>
                  )
                })
              ) : (
                <div className={styles.commandEmpty}>
                  <strong>오늘 새로 할 행동은 없습니다.</strong>
                  <span>장기투자 지표라 매일 신호가 나오지 않는 것이 정상입니다.</span>
                </div>
              )}
            </div>
          </div>
        )}

        {summary && (
          <div className={styles.portfolioSummaryBar}>
            <div className={styles.summaryMain}>
              <span>포트폴리오 요약</span>
              <strong>{displayAmount(summary.total_value)}</strong>
              <em style={{ color: pctColor(summary.total_return_pct) }}>
                {displayPnl((summary.invested_value ?? summary.total_value) - summary.total_cost)}
                {' '}
                {fmtPct(summary.total_return_pct)}
              </em>
            </div>
            <div className={styles.summaryMetric}>
              <span>주식 평가액</span>
              <strong>{displayAmount(summary.invested_value ?? summary.total_value)}</strong>
            </div>
            <div className={styles.summaryMetric}>
              <span>현금</span>
              <strong>{displayAmount(summary.cash_balance ?? cashBalance)}</strong>
            </div>
            <div className={styles.summaryMetric}>
              <span>오늘 등락</span>
              <strong style={{ color: pctColor(summary.daily_change_pct) }}>
                {fmtPct(summary.daily_change_pct)}
              </strong>
            </div>
            <div className={styles.summaryActions}>
              <div className={styles.currencyToggle}>
                <button
                  className={`${styles.currencyBtn} ${currencyMode === 'KRW' ? styles.currencyBtnActive : ''}`}
                  onClick={() => handleCurrencyToggle('KRW')}
                >
                  ₩
                </button>
                <button
                  className={`${styles.currencyBtn} ${currencyMode === 'USD' ? styles.currencyBtnActive : ''}`}
                  onClick={() => handleCurrencyToggle('USD')}
                >
                  $
                </button>
              </div>
              <button
                type="button"
                className={styles.ledgerHistoryBtn}
                onClick={() => setAssetPanelOpen(open => !open)}
              >
                {assetPanelOpen ? '히스토리 닫기' : '자산 히스토리'}
              </button>
            </div>
          </div>
        )}
      </div>

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
                    onChange={(e) => setCashDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCashSave()
                    }}
                    placeholder="0.00"
                    aria-label="현금 보유액"
                  />
                </div>
                <button
                  type="button"
                  className={styles.cashSaveBtn}
                  onClick={handleCashSave}
                  disabled={cashSaving}
                >
                  {cashSaving ? '저장 중…' : '현금 저장'}
                </button>
              </div>
            </div>
          )}

          {assetPanelOpen && (
            <div className={styles.assetPanel}>
              <div className={styles.assetPanelHeader}>
                <div>
                  <div className={styles.assetPanelLabel}>Asset History · {assetPeriodLabel}</div>
                  <div className={styles.assetPanelTitle}>
                    {assetLatest ? displayAmount(assetLatest.totalAssetValue) : displayAmount(summary.total_value)}
                  </div>
                  <div className={styles.assetPanelSub}>
                    총자산은 입출금 포함 · 투자 변화는 주식 평가액 기준 · 기간 시작 {assetStartLabel}
                    {assetFirst?.totalAssetValue != null ? ` · ${displayAmount(assetFirst.totalAssetValue)}` : ''}
                  </div>
                </div>
                <div className={styles.assetPeriodToggle}>
                  {ASSET_HISTORY_PERIODS.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      className={`${styles.assetPeriodBtn} ${assetHistoryPeriod === p.value ? styles.assetPeriodBtnActive : ''}`}
                      onClick={() => setAssetHistoryPeriod(p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className={styles.assetStats}>
                <div>
                  <span>주식 평가액 변화</span>
                  <strong style={{ color: pctColor(investedChangePct) }}>{fmtPct(investedChangePct)}</strong>
                  <em>현금 변동 제외</em>
                </div>
                <div>
                  <span>총자산 변화</span>
                  <strong style={{ color: pctColor(totalFlowPct) }}>{fmtPct(totalFlowPct)}</strong>
                  <em>입출금 포함</em>
                </div>
                <div>
                  <span>고점 대비</span>
                  <strong style={{ color: pctColor(assetDrawdownPct) }}>{fmtPct(assetDrawdownPct)}</strong>
                  <em>현재 총자산 기준</em>
                </div>
                <div>
                  <span>현재 현금</span>
                  <strong>{displayAmount(summary.cash_balance ?? cashBalance)}</strong>
                  <em>총자산에 포함</em>
                </div>
              </div>

              {assetHistoryLoading && (
                <div className={styles.assetState}>히스토리 로딩 중…</div>
              )}
              {!assetHistoryLoading && assetHistoryError && (
                <div className={styles.assetState}>{assetHistoryError}</div>
              )}
              {!assetHistoryLoading && !assetHistoryError && assetChartHistory.length === 0 && (
                <div className={styles.assetState}>아직 자산 히스토리가 없습니다.</div>
              )}
              {!assetHistoryLoading && !assetHistoryError && assetChartHistory.length > 0 && (
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart
                    data={assetChartHistory}
                    margin={{ top: 12, right: 14, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="4 6" stroke="var(--border)" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={fmtAxisDate}
                      tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                      axisLine={false}
                      tickLine={false}
                      tickMargin={8}
                    />
                    <YAxis
                      domain={assetYDomain}
                      tickFormatter={(v) => v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`}
                      tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                      axisLine={false}
                      tickLine={false}
                      width={56}
                    />
                    <Tooltip content={<AssetHistoryTooltip displayAmount={displayAmount} />} />
                    {summary.total_cost != null && (
                      <ReferenceLine
                        y={summary.total_cost}
                        stroke="rgba(163, 170, 184, 0.55)"
                        strokeDasharray="4 4"
                      />
                    )}
                    {assetStartValue != null && (
                      <ReferenceLine
                        y={assetStartValue}
                        stroke="rgba(59, 130, 246, 0.45)"
                        strokeDasharray="5 5"
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="totalAssetValue"
                      stroke="var(--flee)"
                      strokeWidth={2.5}
                      dot={assetChartHistory.length === 1
                        ? { r: 5, fill: 'var(--flee)', strokeWidth: 0 }
                        : false
                      }
                      activeDot={{ r: 5, strokeWidth: 0 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="investedValue"
                      stroke="var(--calm)"
                      strokeWidth={1.8}
                      strokeDasharray="5 5"
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 0 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
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

          {summary && riskWarnings.length > 0 && (
            <div className={styles.riskPanel}>
              <div className={styles.riskPanelHead}>
                <span>포트폴리오 리스크 체크</span>
                <strong>{riskWarnings[0]?.level === 'CLEAR' ? '안정' : `${riskWarnings.length}개 점검`}</strong>
              </div>
              <div className={styles.riskList}>
                {riskWarnings.map((item) => (
                  <div
                    key={`${item.title}-${item.value}`}
                    className={`${styles.riskItem} ${styles[`riskItem_${item.level?.toLowerCase()}`] || ''}`}
                  >
                    <span>{item.title}</span>
                    <strong>{item.value}</strong>
                    <em>{item.detail}</em>
                  </div>
                ))}
              </div>
            </div>
          )}

          {summary && portfolioAlerts.length > 0 && (
            <div className={styles.alertPanel}>
              <div className={styles.alertPanelHead}>
                <span>알림 조건</span>
                <strong>{portfolioAlerts.length}개 활성</strong>
              </div>
              <div className={styles.alertList}>
                {portfolioAlerts.slice(0, 3).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`${styles.alertItem} ${styles[`alertItem_${item.severity?.toLowerCase()}`] || ''}`}
                    onClick={() => item.ticker ? navigate(`/stock/${item.ticker}`) : null}
                  >
                    <span>{alertSeverityLabel(item.severity)}</span>
                    <strong>{item.title}</strong>
                    <em>{item.value} · {item.detail}</em>
                  </button>
                ))}
              </div>
            </div>
          )}

          {signalJournalSummary.totalCount > 0 && (
            <div className={styles.journalOverview}>
              <div className={styles.journalOverviewHead}>
                <div>
                  <span>판단 기록</span>
                  <strong>{formatJournalCount(signalJournalSummary.totalCount)}</strong>
                </div>
                <button
                  type="button"
                  className={styles.journalOverviewLink}
                  onClick={() => navigate('/journal')}
                >
                  전체 기록 보기
                </button>
              </div>
              <div className={styles.journalOverviewStats}>
                <div>
                  <span>매수 총액</span>
                  <strong>{formatJournalAmount(signalJournalSummary.buyAmount) ?? '$0'}</strong>
                  <em>{formatJournalCount(signalJournalSummary.buyCount)}</em>
                </div>
                <div>
                  <span>익절 총액</span>
                  <strong>{formatJournalAmount(signalJournalSummary.sellAmount) ?? '$0'}</strong>
                  <em>{formatJournalCount(signalJournalSummary.sellCount)}</em>
                </div>
                <div>
                  <span>평균 익절률</span>
                  <strong>
                    {signalJournalSummary.hasProfitData
                      ? formatJournalProfit(signalJournalSummary.avgProfitPct)
                      : '—'}
                  </strong>
                  <em>익절 기록 기준</em>
                </div>
              </div>
              {recentSignalLogs.length > 0 && (
                <div className={styles.journalRecentList}>
                  {recentSignalLogs.map((log) => (
                    <button
                      key={log.id}
                      type="button"
                      className={styles.journalRecentItem}
                      onClick={() => navigate(`/stock/${log.ticker}`)}
                    >
                      <strong>{log.ticker}</strong>
                      <span>{log.actionLabel ?? log.actionType ?? '기록'}</span>
                      <em>{formatJournalAmount(log.amount) ?? `HERD ${log.herdScore ?? '—'}`}</em>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ── 종목 카드 그리드 ── */}
      {!loading && !error && portfolio.length > 0 && (
        <>
          <div className={styles.sectionRow}>
            <div className={styles.sectionTitle}>보유 종목 · {portfolio.length}</div>
            <div className={styles.sortTabs} aria-label="보유 종목 정렬">
              {PORTFOLIO_SORT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  className={`${styles.sortTab} ${portfolioSort === option.value ? styles.sortTabActive : ''}`}
                  onClick={() => handlePortfolioSortChange(option.value)}
                  type="button"
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.holdingsTable}>
            <div className={styles.holdingsHeader}>
              <span>종목</span>
              <span>보유 비중</span>
              <span>평가금액</span>
              <span>수익률</span>
              <span>HERD</span>
              <span>신호</span>
            </div>
            {sortedPortfolio.map((item) => {
              const row       = rows.find((r) => r.ticker === item.ticker)
              const herd      = herdMap[item.ticker]
              const stage     = herd?.herdStage ?? 'Calm'
              const color     = stageColor(stage)
              const badge     = badgeStyle(stage)
              const signal    = signalStyle(herd?.signal)
              const stageName = stage.startsWith('Herd ') ? stage.slice(5) : stage
              const herdScore = herd ? Math.round(herd.herdV4 ?? herd.herdScore) : null
              const positionAction = herd ? buildPositionAction(herd, row) : null
              const actionColor = positionAction?.muted ? 'var(--calm)' : signal.color

              const price       = priceMap[item.ticker]
              const hasAvgPrice = item.avgPrice != null && item.quantity != null
              const isDeleting  = deletingTicker === item.ticker

              /* 종목 손익 = 평가금액 - 매입금액(평단가 × 수량) */
              const pnlUsd = (hasAvgPrice && price)
                ? price.market_value - item.avgPrice * item.quantity
                : null

              return (
                <div
                  key={item.ticker}
                  className={`${styles.holdingRow} ${editMode ? styles.holdingRowEdit : ''}`}
                  onClick={editMode ? undefined : () => navigate(`/stock/${item.ticker}`)}
                  style={{ opacity: isDeleting ? 0.4 : 1 }}
                >
                  <div className={styles.cardStripe} style={{ background: color, color }} />

                  {editMode && (
                    <button
                      className={styles.cardDeleteBtn}
                      style={{ opacity: 1 }}
                      onClick={e => handleDelete(e, item.ticker)}
                      disabled={!!deletingTicker}
                      title={`${item.ticker} 포트폴리오에서 삭제`}
                    >
                      {isDeleting ? '…' : '✕'}
                    </button>
                  )}

                  <div className={styles.holdingStockCell}>
                    <StockAvatar
                      ticker={item.ticker}
                      logoUrl={herd?.logoUrl}
                      tone={badge}
                      size="lg"
                    />
                    <div className={styles.holdingStockText}>
                      <strong>{item.ticker}</strong>
                      <span style={{ color }}>
                        {stageName}
                        {herdScore != null ? ` · HERD ${herdScore}` : ''}
                      </span>
                      {shouldShowQuality(herd) && (
                        <em
                          style={{ color: qualityColor(herd.qualityLevel) }}
                          title={qualityReasonText(herd)}
                        >
                          {qualityWarningText(herd)}
                        </em>
                      )}
                    </div>
                  </div>

                  <div className={styles.holdingMetric}>
                    <span>{row ? `${row.currentWeight.toFixed(1)}%` : '—'}</span>
                    <em>{row ? `목표 ${row.targetWeight.toFixed(1)}%` : '목표 —'}</em>
                    {row && <small>{fmtWeightGap(row)}</small>}
                  </div>

                  <div className={styles.holdingMetric}>
                    <span>{price ? displayAmount(price.market_value) : '—'}</span>
                    <em>{hasAvgPrice ? `보유 ${fmtShares(item.quantity)}` : '수량 미입력'}</em>
                    {hasAvgPrice && <small>평단 {displayAmount(item.avgPrice)}</small>}
                  </div>

                  <div className={styles.holdingMetric}>
                    <span style={{ color: pctColor(price?.return_pct) }}>
                      {price ? fmtPct(price.return_pct) : '—'}
                    </span>
                    <em style={{ color: pctColor(price?.return_pct) }}>
                      {pnlUsd != null ? displayPnl(pnlUsd) : '평단 필요'}
                    </em>
                    {price && (
                      <small style={{ color: pctColor(price.daily_change_pct) }}>
                        오늘 {fmtPct(price.daily_change_pct)}
                      </small>
                    )}
                  </div>

                  <div className={styles.holdingHerdCell}>
                    {herd ? (
                      <>
                        <strong style={{ color }}>{herdScore}</strong>
                        <span style={{ color }}>{stageName}</span>
                        {formatSignalAgeLabel(herd) && <em>{formatSignalAgeLabel(herd)}</em>}
                      </>
                    ) : (
                      <span className={styles.cardDash}>—</span>
                    )}
                  </div>

                  <div className={styles.holdingActionCell}>
                    {herd ? (
                      <>
                        <strong style={{ color: actionColor }}>{positionAction.code}</strong>
                        <span>{positionAction.text}</span>
                        <em>{positionAction.basis}</em>
                      </>
                    ) : (
                      <span className={styles.cardDash}>—</span>
                    )}
                  </div>

                  {editMode && (
                    <div className={styles.holdingEditTray} onClick={e => e.stopPropagation()}>
                      <button
                        className={styles.cardInputBtn}
                        onClick={e => {
                          e.stopPropagation()
                          setModalTicker(item.ticker)
                        }}
                      >
                        {hasAvgPrice ? '평단·수량 수정' : '평단·수량 입력'}
                      </button>
                      {row && (
                        <div className={styles.targetEditRow}>
                          <label className={styles.targetLabel} htmlFor={`target-${item.ticker}`}>
                            목표 비중
                          </label>
                          <div className={styles.targetInputWrap}>
                            <input
                              id={`target-${item.ticker}`}
                              className={styles.targetInput}
                              type="number"
                              min="0"
                              max="100"
                              step="1"
                              value={targetWeights[item.ticker] ?? ''}
                              placeholder={row.targetWeight.toFixed(0)}
                              onChange={e => handleTargetWeightChange(item.ticker, e.target.value)}
                              aria-label={`${item.ticker} 목표 비중`}
                            />
                            <span>%</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
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
