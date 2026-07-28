import PriceHerdTimelineChart from '../../components/PriceHerdTimelineChart/PriceHerdTimelineChart'
import styles from './StockDetail.module.css'
import { HISTORY_PERIODS } from './stockDetailModel'

export default function StockDetailHistory({
  period,
  onPeriodChange,
  loading,
  points,
  currentScore,
  episodeStudy,
  episodeLoading,
  historicalContext,
  historicalContextLoading,
  timelineMeta,
  observation,
}) {
  return (
    <section id="stock-history" className={styles.historySection} aria-labelledby="stock-history-title">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="stock-history-title">가격 · HERD 이력</h2>
          <span>수정 종가 · 주간 관찰</span>
        </div>
        <div className={styles.historyTabs}>
          {HISTORY_PERIODS.map((item) => (
            <button
              key={item.value}
              className={`${styles.historyTab} ${period === item.value ? styles.historyTabActive : ''}`}
              onClick={() => onPeriodChange(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className={styles.historyBody}>
        {loading ? (
          <div className={styles.chartEmpty}>로딩 중…</div>
        ) : (
          <PriceHerdTimelineChart points={points} currentScore={currentScore} />
        )}
      </div>
      <EpisodeSummary
        historicalContext={historicalContext}
        historicalLoading={historicalContextLoading}
        liveStudy={episodeStudy}
        liveLoading={episodeLoading}
      />
      <DataBasis timeline={timelineMeta} observation={observation} />
    </section>
  )
}

function DataBasis({ timeline, observation }) {
  const observed = timeline?.observationCount ?? 0
  const priced = timeline?.pricedObservationCount ?? 0
  return (
    <dl className={styles.dataBasis} aria-label="데이터 기준">
      <div>
        <dt>모델</dt>
        <dd>{observation?.stateModelVersion ?? timeline?.stateModelVersion ?? 'HERD_STATE_S1'}</dd>
      </div>
      <div>
        <dt>관찰일</dt>
        <dd>{observation?.observationDate ?? '—'}</dd>
      </div>
      <div>
        <dt>가격</dt>
        <dd>{timeline?.priceField === 'ADJUSTED_CLOSE' ? '수정 종가' : '—'}</dd>
      </div>
      <div>
        <dt>가격 연결</dt>
        <dd>{priced}/{observed}</dd>
      </div>
      <div>
        <dt>상태</dt>
        <dd>{observation?.freshnessStatus === 'FRESH' ? '최신' : '확인 필요'}</dd>
      </div>
    </dl>
  )
}

function signedPercent(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number > 0 ? '+' : ''}${number.toFixed(1)}%`
}

function EpisodeSummary({
  historicalContext,
  historicalLoading,
  liveStudy,
  liveLoading,
}) {
  if (historicalLoading) {
    return <div className={styles.episodeNote}>과거 상태 경로 계산 중…</div>
  }
  if (
    historicalContext?.availabilityStatus === 'AVAILABLE'
    && historicalContext?.summaries?.length > 0
  ) {
    const scope = historicalContext.contextScope === 'TICKER_HISTORY'
      ? '이 종목 이력'
      : '현재 구성 종목 참조'
    const liveEpisodes = liveStudy?.episodeCount ?? 0
    return (
      <div className={styles.episodeStudy}>
        <div className={styles.episodeHeader}>
          <div>
            <strong>과거 같은 {historicalContext.herdStage} 진입 이후</strong>
            <span>{scope} · 상태 진입 1회를 한 사건으로 집계</span>
          </div>
          <span>{historicalContext.episodeCount}회 진입</span>
        </div>
        <div className={styles.episodeGrid}>
          {historicalContext.summaries.map((summary) => (
            <div key={summary.horizonSessions} className={styles.episodeMetric}>
              <span>
                {horizonLabel(summary.horizonSessions)} · {summary.completedEpisodes}건
              </span>
              <strong>{signedPercent(summary.medianReturnPct)}</strong>
              <small>
                상승 {Number(summary.positiveRatePct).toFixed(0)}%
                {' · '}중간 최대낙폭 {signedPercent(summary.medianMaePct)}
              </small>
            </div>
          ))}
        </div>
        <p className={styles.episodeDisclaimer}>
          현재 구성 종목의 과거 기술 통계입니다. 상장폐지 종목을 모두 포함하지 않아
          방향 예측이나 매수·매도 판단에는 사용하지 않습니다.
          {!liveLoading && liveEpisodes > 0 ? ` 실제 저장 관찰 ${liveEpisodes}건.` : ''}
        </p>
      </div>
    )
  }

  if (!liveStudy || liveStudy.availabilityStatus !== 'AVAILABLE') return null
  const insufficient = liveStudy.evidenceStatus === 'INSUFFICIENT_SAMPLE'

  return (
    <div className={styles.episodeStudy}>
      <div className={styles.episodeHeader}>
        <div>
          <strong>같은 {liveStudy.herdStage} 진입 이후</strong>
          <span>상태 진입 1회를 한 사건으로 집계</span>
        </div>
        <span>{liveStudy.episodeCount}회 진입</span>
      </div>
      {insufficient ? (
        <div className={styles.episodeNote}>
          완결 표본이 {liveStudy.minimumCompletedEpisodes}개 미만입니다. 방향 판단에는 사용하지 않습니다.
        </div>
      ) : (
        <div className={styles.episodeGrid}>
          {liveStudy.summaries.map((summary) => (
            <div key={summary.weeks} className={styles.episodeMetric}>
              <span>{summary.weeks}주 후 · {summary.completedCount}건</span>
              <strong>{signedPercent(summary.medianReturnPct)}</strong>
              <small>
                상승 {Number(summary.positiveRatePct).toFixed(0)}% · 중간 최대낙폭 {signedPercent(summary.medianMaxDrawdownPct)}
              </small>
            </div>
          ))}
        </div>
      )}
      <p className={styles.episodeDisclaimer}>과거 경로의 기술 통계이며 매수·매도 적중률이 아닙니다.</p>
    </div>
  )
}

function horizonLabel(sessions) {
  if (sessions === 21) return '1개월 후'
  if (sessions === 63) return '3개월 후'
  if (sessions === 126) return '6개월 후'
  return `${sessions}거래일 후`
}
