/**
 * StockDetail.jsx — 종목 상세 페이지 (/stock/:ticker)
 *
 * 구성:
 *   1) 브레드크럼 + 종목 헤더 (배지 + 포트폴리오/관심종목 추가 버튼)
 *   2) HERD 카드 → Action Layer → 신호 근거/지표 → 신뢰도 → 히스토리 → 재무 가드 → 판단 기록
 *
 * API: getStockHerd(ticker), getStockFinancials(ticker), addToPortfolio(ticker), addToWatchlist(ticker)
 * 래퍼런스: wireframes/wireframe-detail.html
 */

import { useParams, useNavigate }                    from 'react-router-dom'
import HerdDots from '../../components/HerdDots/HerdDots'
import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import StockAvatar from '../../components/StockAvatar/StockAvatar'
import SignalJournalModal from '../../components/SignalJournalModal/SignalJournalModal'
import DecisionFlow from '../../components/DecisionFlow/DecisionFlow'
import { qualityReasonText, qualityWarningText, shouldShowQuality } from '../../utils/dataQuality'
import { formatSignalAgeLabel, formatSignalDurationDetail } from '../../utils/signalDuration'
import styles      from './StockDetail.module.css'
import { useStockDetail } from './useStockDetail'
import StockDetailFundamentals from './StockDetailFundamentals'
import StockDetailJournal from './StockDetailJournal'

import {
  BTN_LABELS,
  HISTORY_PERIODS,
  INDICATORS,
  badgeColors,
  epsMultiplierDesc,
  evidenceTone,
  fmtAnnualActions,
  fmtReliabilityPct,
  fmtReliabilityPlainPct,
  fmtReliabilityScore,
  formatActionBasis,
  formatActionMeta,
  formatActionRatio,
  formatIndicator,
  formatMultiplier,
  getTimingSignal,
  normalizeBar,
  reliabilityTone,
  sampleQualityLabel,
  sectorMultiplierDesc,
  signalEdgeLabel,
} from './stockDetailModel'
/* ── 컴포넌트 ─────────────────────────────── */

export default function StockDetail() {
  const { ticker } = useParams()
  const navigate   = useNavigate()
  const {
    herdData, loading, error,
    portfolioStatus, watchlistStatus,
    historyPeriod, setHistoryPeriod, historyLoading,
    reliability, reliabilityLoading,
    financials, financialsLoading,
    signalLogs, journalAction, setJournalAction, actionError,
    normalizedTicker, fetchData,
    handleAddPortfolio, handleAddWatchlist,
    herdScore, herdStage, stageDisp, color, sigStyle,
    qualityToneColor, actionColor, decision,
    currentReliability, reliabilityEvidence,
    fundamentalGuard, signalEvidence, journalSummary,
    historyPoints, herdMomentum,
    handleJournalAction, handleJournalDelete,
  } = useStockDetail(ticker)

  return (
    <div>

      {/* ── 브레드크럼 ── */}
      <div className={styles.breadcrumb}>
        <span className={styles.breadcrumbLink} onClick={() => navigate('/app')}>
          포트폴리오
        </span>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{normalizedTicker}</span>
      </div>

      {/* ── 종목 헤더 ── */}
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

      {/* ── 로딩 ── */}
      {loading && (
        <div className={styles.loadingState}>
          <span className={styles.loadingText}>로딩 중…</span>
        </div>
      )}

      {/* ── 에러 ── */}
      {!loading && error && (
        <div className={styles.errorState}>
          {error.split('\n').map((line, i) => (
            <p key={i} className={i === 0 ? styles.errorTitle : styles.errorSub}>
              {line}
            </p>
          ))}
          <button className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
        </div>
      )}

      {/* ── 핵심 컨텐츠 ── */}
      {!loading && !error && herdData && (
        <div className={styles.contentGrid}>

          {/* ─── 왼쪽 메인 ─── */}
          <div className={styles.colMain}>

            {/* HERD 카드 */}
            <div className={styles.herdCard}>

              {/* 좌: 점수 + 시그널 */}
              <div className={styles.herdScoreSide}>
                <div className={styles.herdEyebrow}>HERD Index</div>
                <div className={styles.herdBigScore} style={{ color }}>
                  {Math.round(herdScore)}
                </div>
                <div className={styles.herdBigStage} style={{ color }}>
                  {stageDisp}
                </div>
                {/* Timing Signal 배지 */}
                <div
                  className={styles.timingSignal}
                  style={{ background: sigStyle.bg, color: sigStyle.color }}
                >
                  {getTimingSignal(herdScore)}
                </div>
                {shouldShowQuality(herdData) && (
                  <>
                    <div
                      className={styles.qualityPill}
                      style={{ color: qualityToneColor, borderColor: qualityToneColor }}
                      title={qualityReasonText(herdData)}
                    >
                      {qualityWarningText(herdData, { pointSuffix: true })}
                    </div>
                    <div className={styles.qualityReason}>{qualityReasonText(herdData)}</div>
                  </>
                )}
              </div>

              {/* 우: HerdDots + 스펙트럼 */}
              <div className={styles.herdAnimSide}>
                <HerdDots
                  score={herdScore}
                  momentum={herdMomentum.delta ?? (herdScore - 50) / 3}
                  actionRatio={herdData.actionRatio ?? 0}
                  enhanced
                  fill
                  dotCount={55}
                />
                {/* 하단 고정: SpectrumBar + 5단계 라벨 */}
                <div className={styles.herdAnimBottom}>
                  <SpectrumBar score={herdScore} height={3} />
                  <div className={styles.spectrumLabels}>
                    <span>Flee 군중 이탈</span>
                    <span>Scatter 군중 흩어짐</span>
                    <span>Calm 군중 균형</span>
                    <span>Drift 군중 쏠림</span>
                    <span>Rush 군중 밀집</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Layer 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>Action Layer</div>
                <div className={styles.cardMeta}>{formatActionMeta(herdData)}</div>
              </div>
              <div className={styles.cardBody}>
                {herdData.actionModelStatus === 'RESEARCH_VALIDATION' && (
                  <div className={styles.actionWarningList} role="status">
                    <span>{herdData.actionDisclaimer ?? '연구 검증 중인 행동 보조 정보입니다.'}</span>
                  </div>
                )}
                <div className={styles.decisionHero}>
                  <div>
                    <div className={styles.decisionLabel}>타이밍 액션</div>
                    <div className={styles.decisionTitle}>
                      {herdData.actionLabel ?? decision.title}
                    </div>
                    <div className={styles.decisionSubtitle}>
                      {herdData.actionRegimeLabel ?? decision.subtitle}
                    </div>
                    <div className={styles.decisionBasis}>
                      {formatActionBasis(herdData)}
                    </div>
                    {formatSignalDurationDetail(herdData) && (
                      <div className={styles.decisionBasis}>
                        {formatSignalAgeLabel(herdData)}
                      </div>
                    )}
                    <div className={`${styles.decisionMomentum} ${styles[`decisionMomentum_${herdMomentum.tone}`] || ''}`}>
                      <span>{herdMomentum.label}</span>
                      <strong>{herdMomentum.detail}</strong>
                    </div>
                  </div>
                  <div className={styles.decisionPill} style={{ color: actionColor, borderColor: actionColor }}>
                    {formatActionRatio(herdData.actionRatio)}
                  </div>
                </div>
                <DecisionFlow herd={herdData} />
                <div className={styles.decisionList}>
                  {(herdData.actionReasons?.length ? herdData.actionReasons : decision.notes).slice(0, 2).map((note) => (
                    <div key={note} className={styles.decisionItem}>{note}</div>
                  ))}
                </div>
                {Array.isArray(herdData.actionWarnings) && herdData.actionWarnings.length > 0 && (
                  <div className={styles.actionWarningList}>
                    {herdData.actionWarnings.slice(0, 1).map((warning) => (
                      <span key={warning}>{warning}</span>
                    ))}
                  </div>
                )}
                {herdData.oosValidationSummary && (
                  <div className={styles.decisionBasis}>{herdData.oosValidationSummary}</div>
                )}
              </div>
            </div>

            <details className={styles.detailDisclosure}>
              <summary>
                <div><span>상세 분석</span><strong>신호 근거·지표 분해·검증 결과</strong></div>
                <em>펼쳐보기</em>
              </summary>
              <div className={styles.detailDisclosureBody}>
            {/* 신호 근거 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>신호 근거</div>
                  <div className={styles.cardMeta}>현재 HERD 판단을 움직인 데이터</div>
                </div>
                <div className={styles.cardMeta}>{herdData.scoreDate} 기준</div>
              </div>
              <div className={styles.cardBodySmall}>
                <div className={styles.evidenceGrid}>
                  {signalEvidence.map((item) => (
                    <div key={`${item.label}-${item.caption}`} className={styles.evidenceItem}>
                      <span>{item.label}</span>
                      <strong style={{ color: evidenceTone(item.type) }}>{item.value}</strong>
                      <em>{item.caption}</em>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 지표 분해 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>지표 분해</div>
                <div className={styles.cardMeta}>
                  {herdData.scoreDate} 기준
                </div>
              </div>
              <div className={styles.cardBody}>
                {INDICATORS.map((ind) => {
                  /*
                   * API 응답에 없는 필드는 undefined → null로 처리.
                   */
                  const raw    = herdData[ind.key] ?? null
                  const hasVal = raw != null
                  const pct    = hasVal ? normalizeBar(raw, ind.min, ind.max) : 0
                  const disp   = raw != null ? formatIndicator(raw, ind.unit, ind.signed) : '—'

                  return (
                    <div
                      key={ind.key}
                      className={styles.indicatorRow}
                    >
                      {/* 지표명 */}
                      <div className={styles.indicatorLabel}>{ind.label}</div>

                      {/* 가중치 — 비활성 항목은 "비활성" 텍스트 */}
                      <div className={styles.indicatorWeight}>
                        {ind.weight}%
                      </div>

                      {/* 프로그레스 바 — 값 없으면 빈 트랙만 */}
                      <div className={styles.indicatorTrack}>
                        {hasVal && (
                          <div
                            className={styles.indicatorFill}
                            style={{ width: `${pct}%`, background: color }}
                          />
                        )}
                      </div>

                      {/* 수치 */}
                      <div className={styles.indicatorValue}>{disp}</div>
                    </div>
                  )
                })}
                <div className={styles.adjustmentBox}>
                  <div className={styles.adjustmentRow}>
                    <span>EPS 보정</span>
                    <strong>
                      {formatMultiplier(herdData.epsMultiplier)}
                      <em>{epsMultiplierDesc(herdData.epsMultiplier)}</em>
                    </strong>
                  </div>
                  <div className={styles.adjustmentRow}>
                    <span>섹터 강도 보정</span>
                    <strong>
                      {formatMultiplier(herdData.sectorMultiplier)}
                      <em>{sectorMultiplierDesc(herdData.sectorMultiplier)}</em>
                    </strong>
                  </div>
                </div>
              </div>
            </div>

            {/* HERD 신호 신뢰도 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>신호 검증</div>
                  <div className={styles.cardMeta}>최근 3년 HERD 히스토리</div>
                </div>
                {reliability && (
                  <div
                    className={styles.reliabilityBadge}
                    style={{
                      color: reliabilityTone(reliability.reliabilityGrade),
                      borderColor: reliabilityTone(reliability.reliabilityGrade),
                    }}
                  >
                    {reliability.reliabilityLabel}
                  </div>
                )}
              </div>
              <div className={styles.cardBodySmall}>
                {reliabilityLoading ? (
                  <div className={styles.chartEmpty}>로딩 중…</div>
                ) : reliability ? (
                  <>
                    {currentReliability && (
                      <div className={styles.currentReliability}>
                        <div>
                          <span>{currentReliability.label}</span>
                          <strong>
                            {currentReliability.scoreValue
                              ? fmtReliabilityScore(currentReliability.value)
                              : fmtReliabilityPlainPct(currentReliability.value)}
                          </strong>
                        </div>
                        <em>
                          {currentReliability.caption}
                          {currentReliability.sample != null ? ` · ${currentReliability.sample}회` : ''}
                        </em>
                      </div>
                    )}
                    <div className={styles.reliabilityGrid}>
                      <div className={styles.reliabilityItem}>
                        <span>모델 적합도</span>
                        <strong>{fmtReliabilityScore(reliability.fitScore)}</strong>
                        <em>{reliability.reliabilityLabel}</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>표본 품질</span>
                        <strong>{sampleQualityLabel(reliability.sampleQuality)}</strong>
                        <em>{reliability.totalSignalSamples ?? 0}회</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>Flee 적중률</span>
                        <strong>{fmtReliabilityPlainPct(reliability.fleeHitRate)}</strong>
                        <em>{signalEdgeLabel(reliability.buySignalEdge)}</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>Rush 적중률</span>
                        <strong>{fmtReliabilityPlainPct(reliability.rushHitRate)}</strong>
                        <em>{signalEdgeLabel(reliability.sellSignalEdge)}</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>MDD 개선</span>
                        <strong>{fmtReliabilityPct(reliability.mddImprovement, '%p')}</strong>
                        <em>낙폭 관리</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>수익률 보존</span>
                        <strong>{fmtReliabilityPlainPct(reliability.returnPreservation)}</strong>
                        <em>Buy & Hold 대비</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>연 행동 수</span>
                        <strong>{fmtAnnualActions(reliability.annualActions)}</strong>
                        <em>과매매 체크</em>
                      </div>
                    </div>
                    {reliabilityEvidence.length > 0 && (
                      <div className={styles.reliabilityEvidenceGrid}>
                        {reliabilityEvidence.map((item) => (
                          <div
                            key={item.label}
                            className={`${styles.reliabilityEvidenceItem} ${styles[`reliabilityEvidence_${item.tone}`] || ''}`}
                          >
                            <span>{item.label}</span>
                            <strong>{item.value}</strong>
                            <em>{item.caption}</em>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className={styles.reliabilitySummary}>
                      {reliability.reliabilityVerdict ?? reliability.summary}
                    </div>
                  </>
                ) : (
                  <div className={styles.chartEmpty}>신뢰도 데이터를 계산할 수 없습니다.</div>
                )}
              </div>
            </div>
              </div>
            </details>

            {/* HERD 히스토리 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>HERD Index History</div>
                  <div className={styles.cardMeta}>1M · 3M · 1Y · 3Y</div>
                </div>
                <div className={styles.historyTabs}>
                  {HISTORY_PERIODS.map((p) => (
                    <button
                      key={p.value}
                      className={`${styles.historyTab} ${historyPeriod === p.value ? styles.historyTabActive : ''}`}
                      onClick={() => setHistoryPeriod(p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className={styles.cardBody}>
                {historyLoading ? (
                  <div className={styles.chartEmpty}>로딩 중…</div>
                ) : (
                  <HerdHistoryChart
                    points={historyPoints}
                    currentScore={herdScore}
                    height={230}
                  />
                )}
              </div>
            </div>

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
                  onCreate={setJournalAction}
                  onDelete={handleJournalDelete}
                />
              </div>
            </details>

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
