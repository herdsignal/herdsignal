import HerdDots from '../../components/HerdDots/HerdDots'
import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import styles from './Dashboard.module.css'
import {
  HISTORY_PERIODS,
  fmtAxisDate,
  fmtPct,
  fmtScoreDate,
  fmtTime,
  pctColor,
  scoreToColor,
  scoreToStage,
  stageColor,
  stageDesc,
} from './dashboardModel'

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

export default function DashboardCommandCenter({
  spyData,
  spyScore,
  spyStage,
  spyMomentum,
  spyTab,
  onSpyTabChange,
  d1AvgPoint,
  m1AvgPoint,
  y1AvgPoint,
  lastUpdated,
  marketDataDate,
  spyHistoryPeriod,
  onSpyHistoryPeriodChange,
  spyHistoryLoading,
  spyHistory,
  summary,
  displayAmount,
  displayPnl,
  cashBalance,
  currencyMode,
  onCurrencyToggle,
  assetPanelOpen,
  onToggleAssetPanel,
  onOpenModelReport,
}) {
  return (
    <div className={styles.commandFrame}>
      <div className={styles.commandFrameTop}>
        <div>
          <span>Signal Command Center</span>
          <strong>현재 시장 신호</strong>
          <em>S&amp;P 500 흐름과 보유 종목 행동 대기열을 함께 확인합니다.</em>
        </div>
        <div className={styles.commandFrameMeta}>
          <span>
            {lastUpdated
              ? `${marketDataDate ? `종가 ${fmtAxisDate(marketDataDate)} · ` : ''}업데이트 · ${fmtTime(lastUpdated)}`
              : '업데이트 대기'}
          </span>
          <button type="button" onClick={onOpenModelReport}>모델 리포트</button>
        </div>
      </div>

      <div className={styles.marketBanner}>
        <div className={styles.bannerScoreBlock}>
          <div className={styles.bannerEyebrow}>SPY · S&amp;P 500 · 운영 HERD v4</div>
          <div className={styles.bannerScore} style={{ color: stageColor(spyStage) }}>
            {spyData ? Math.round(spyScore) : '—'}
          </div>
          <div className={styles.bannerStage} style={{ color: stageColor(spyStage) }}>
            {spyStage.startsWith('Herd ') ? spyStage : `Herd ${spyStage}`}
          </div>
          <div className={styles.bannerDesc}>{stageDesc(spyStage)}</div>
        </div>

        <div className={styles.bannerRight}>
          <div className={styles.bannerTabs}>
            <button
              className={`${styles.bannerTab} ${spyTab === 'overview' ? styles.bannerTabActive : ''}`}
              onClick={() => onSpyTabChange('overview')}
            >Overview</button>
            <button
              className={`${styles.bannerTab} ${spyTab === 'timeline' ? styles.bannerTabActive : ''}`}
              onClick={() => onSpyTabChange('timeline')}
            >Timeline</button>
          </div>

          {spyTab === 'overview' && (
            <div className={styles.bannerOverview}>
              <div className={styles.bannerAnimBlock}>
                <HerdDots
                  score={spyScore}
                  momentum={spyMomentum.delta ?? (spyScore - 50) / 3}
                  actionRatio={spyData?.actionRatio ?? 0}
                  enhanced
                  fill
                  dotCount={84}
                />
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

          {spyTab === 'timeline' && (
            <div className={styles.bannerTimeline}>
              <div className={styles.bannerPeriodTabs}>
                {HISTORY_PERIODS.map((period) => (
                  <button
                    key={period.value}
                    className={`${styles.bannerPeriodTab} ${spyHistoryPeriod === period.value ? styles.bannerPeriodTabActive : ''}`}
                    onClick={() => onSpyHistoryPeriodChange(period.value)}
                  >
                    {period.label}
                  </button>
                ))}
              </div>
              {spyHistoryLoading ? (
                <div className={styles.bannerTimelineEmpty}>로딩 중…</div>
              ) : spyHistory.length === 0 ? (
                <div className={styles.bannerTimelineEmpty}>데이터 없음</div>
              ) : (
                <HerdHistoryChart points={spyHistory} currentScore={spyScore} height={190} />
              )}
            </div>
          )}
        </div>
      </div>

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
              {['KRW', 'USD'].map((mode) => (
                <button
                  key={mode}
                  className={`${styles.currencyBtn} ${currencyMode === mode ? styles.currencyBtnActive : ''}`}
                  onClick={() => onCurrencyToggle(mode)}
                >
                  {mode === 'KRW' ? '₩' : '$'}
                </button>
              ))}
            </div>
            <button type="button" className={styles.ledgerHistoryBtn} onClick={onToggleAssetPanel}>
              {assetPanelOpen ? '히스토리 닫기' : '자산 히스토리'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
