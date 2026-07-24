import HerdDots from '../../components/HerdDots/HerdDots'
import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import {
  scoreColor,
  stageColor,
  stageDescription,
  stageLabelFromScore,
} from '../../utils/herdStage'
import { HERD_HISTORY_PERIODS } from '../../utils/historyPeriods'
import sharedStyles from './Watchlist.module.css'
import componentStyles from './WatchlistMarketBanner.module.css'

const styles = { ...sharedStyles, ...componentStyles }

export default function WatchlistMarketBanner({
  spyData,
  spyHistory,
  spyHistoryPeriod,
  setSpyHistoryPeriod,
  spyHistoryLoading,
  spyTab,
  setSpyTab,
  spyScore,
  spyStage,
  d1AvgPoint,
  m1AvgPoint,
  y1AvgPoint,
  spyMomentum,
}) {
  return (
    <div className={styles.marketBanner}>
      <div className={styles.bannerScoreBlock}>
        <div className={styles.bannerEyebrow}>S&amp;P 500 HERD Index</div>
        <div className={styles.bannerScore} style={{ color: stageColor(spyStage) }}>
          {spyData ? Math.round(spyScore) : '—'}
        </div>
        <div className={styles.bannerStage} style={{ color: stageColor(spyStage) }}>
          {spyStage.startsWith('Herd ') ? spyStage : `Herd ${spyStage}`}
        </div>
        <div className={styles.bannerDesc}>{stageDescription(spyStage)}</div>
      </div>

      <div className={styles.bannerRight}>
        <div className={styles.bannerTabs}>
          <button
            className={`${styles.bannerTab} ${spyTab === 'overview' ? styles.bannerTabActive : ''}`}
            onClick={() => setSpyTab('overview')}
          >
            Overview
          </button>
          <button
            className={`${styles.bannerTab} ${spyTab === 'timeline' ? styles.bannerTabActive : ''}`}
            onClick={() => setSpyTab('timeline')}
          >
            Timeline
          </button>
        </div>

        {spyTab === 'overview' ? (
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
                <div className={styles.bannerStatLabel}>업데이트</div>
                <div className={styles.bannerStatUpdate}>
                  {spyData ? formatScoreDate(spyData.scoreDate) : '—'}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className={styles.bannerTimeline}>
            <div className={styles.bannerPeriodTabs}>
              {HERD_HISTORY_PERIODS.map((period) => (
                <button
                  key={period.value}
                  className={`${styles.bannerPeriodTab} ${spyHistoryPeriod === period.value ? styles.bannerPeriodTabActive : ''}`}
                  onClick={() => setSpyHistoryPeriod(period.value)}
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
  )
}

function BannerStat({ label, point }) {
  const stage = stageLabelFromScore(point?.score, true)
  return (
    <div className={styles.bannerStatItem}>
      <div className={styles.bannerStatLabel}>{label}</div>
      {point && stage ? (
        <>
          <div className={styles.bannerStatMain}>
            <span className={styles.bannerStatValue} style={{ color: scoreColor(point.score) }}>
              {Math.round(point.score)}
            </span>
            <span className={styles.bannerStatStage}>{stage}</span>
          </div>
          <div className={styles.bannerStatDesc}>{stageDescription(stage)}</div>
        </>
      ) : <div className={styles.bannerStatValue}>—</div>}
    </div>
  )
}

function formatScoreDate(dateString) {
  if (!dateString) return '—'
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Seoul' }))
  const pad = (value) => String(value).padStart(2, '0')
  const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  const yesterdayDate = new Date(now)
  yesterdayDate.setDate(yesterdayDate.getDate() - 1)
  const yesterday = `${yesterdayDate.getFullYear()}-${pad(yesterdayDate.getMonth() + 1)}-${pad(yesterdayDate.getDate())}`
  if (dateString === today) return '오늘'
  if (dateString === yesterday) return '어제'

  const date = new Date(dateString)
  return Number.isNaN(date.getTime())
    ? dateString
    : date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}
