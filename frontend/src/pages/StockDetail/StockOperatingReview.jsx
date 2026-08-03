import styles from './StockDetail.module.css'
import {
  AREA_LABELS,
  STATUS_LABELS,
  businessFacts,
  guidanceFacts,
  integrityLabel,
  marketFacts,
  normalized,
  pct,
  pricePathValue,
  recordDate,
  signedPercentagePoint,
} from './stockOperatingReviewModel'

export default function StockOperatingReview({ state }) {
  const view = normalized(state.review)
  const verifiedBusinessFacts = businessFacts(view?.objective)
  const verifiedGuidanceFacts = guidanceFacts(view?.objective)
  const verifiedMarketFacts = marketFacts(view?.objective)
  const latestRecord = state.records[0] ?? null

  return (
    <section id="stock-operating-review" className={styles.operatingSection}>
      <header className={styles.operatingHeader}>
        <div>
          <span>LONG-TERM REVIEW</span>
          <h2>장기 운용 검토</h2>
        </div>
        {view && (
          <div className={styles.operatingDecision}>
            <strong>{view.status}</strong>
            <small>{view.headline}</small>
          </div>
        )}
      </header>

      {state.loading && <p className={styles.operatingEmpty}>근거 확인 중…</p>}
      {!state.loading && state.error && (
        <p className={styles.operatingEmpty} role="status">{state.error}</p>
      )}
      {!state.loading && view && (
        <>
          <div className={styles.operatingAreas}>
            {(view.objective?.assessments ?? []).map((area) => (
              <div key={area.area}>
                <span>{AREA_LABELS[area.area] ?? area.area}</span>
                <strong>{STATUS_LABELS[area.status] ?? area.status}</strong>
                <small>{area.headline}</small>
              </div>
            ))}
          </div>

          {verifiedBusinessFacts.length > 0 && (
            <div className={styles.operatingBusinessFacts}>
              <div>
                <span>SEC PIT</span>
                <small>{verifiedBusinessFacts[0].asOfDate} 접수 기준</small>
              </div>
              {verifiedBusinessFacts.map((fact) => (
                <dl key={fact.id}>
                  <dt>{fact.label}</dt>
                  <dd>{fact.primaryValue}</dd>
                  <small>
                    {fact.primaryLabel}
                    {fact.secondaryValue ? ` · ${fact.secondaryLabel} ${fact.secondaryValue}` : ''}
                  </small>
                </dl>
              ))}
            </div>
          )}


          {verifiedGuidanceFacts.length > 0 && (
            <div className={styles.operatingGuidanceFacts}>
              <div>
                <span>SEC GUIDANCE</span>
                <small>
                  {verifiedGuidanceFacts[0].asOfDate} 접수 · 방향 판정 아님 · 컨센서스/PIT 밸류 미연결
                </small>
              </div>
              {verifiedGuidanceFacts.map((fact) => (
                <dl key={fact.id}>
                  <dt>{fact.label}</dt>
                  <dd>{fact.value}</dd>
                </dl>
              ))}
            </div>
          )}

          {verifiedMarketFacts.length > 0 && (
            <div className={styles.operatingMarketFacts}>
              <div>
                <span>MARKET CONTEXT</span>
                <small>{verifiedMarketFacts[0].asOfDate} 종가 · 설명 전용</small>
              </div>
              {verifiedMarketFacts.map((fact) => (
                <dl key={fact.id}>
                  <dt>{fact.label}</dt>
                  <dd>{fact.displayValue}</dd>
                </dl>
              ))}
            </div>
          )}

          {(view.mandate || view.portfolioFit) && (
            <dl className={styles.operatingContext}>
              <div>
                <dt>투자 기간</dt>
                <dd>{view.mandate?.timeHorizonYears ?? '—'}년</dd>
              </div>
              <div>
                <dt>현재 종목 비중</dt>
                <dd>{pct(view.portfolioFit?.currentTickerWeight)}</dd>
              </div>
              <div>
                <dt>현금 비중</dt>
                <dd>{pct(view.portfolioFit?.currentCashRatio)}</dd>
              </div>
              <div>
                <dt>주식 목표 차이</dt>
                <dd>{signedPercentagePoint(view.portfolioFit?.equityTargetGap)}</dd>
              </div>
              <div>
                <dt>행동 가능 비율</dt>
                <dd>{pct(view.mandate?.effectiveActionRatioCap)}</dd>
              </div>
              <div>
                <dt>행동 권한</dt>
                <dd>{view.veto?.actionBlocked ? '차단' : '확인'}</dd>
              </div>
            </dl>
          )}

          {view.limitations.length > 0 && (
            <ul className={styles.operatingLimits} aria-label="판단 제한">
              {view.limitations.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
            </ul>
          )}

          {latestRecord && (
            <div className={styles.operatingPricePath}>
              <div>
                <span>저장 판단 이후 가격 경로</span>
                <small>
                  {recordDate(latestRecord.referencePriceDate)} 종가 기준 · 성공 판정 아님
                  {' · '}
                  <b data-integrity={latestRecord.integrityStatus ?? 'UNKNOWN'}>
                    {integrityLabel(latestRecord.integrityStatus)}
                  </b>
                </small>
              </div>
              {(latestRecord.outcomes ?? []).map((outcome) => (
                <dl key={outcome.horizonMonths}>
                  <dt>{outcome.horizonMonths}개월</dt>
                  <dd className={
                    outcome.status === 'AVAILABLE' && Number(outcome.priceReturnPct) < 0
                      ? styles.pathNegative
                      : outcome.status === 'AVAILABLE' ? styles.pathPositive : ''
                  }>
                    {pricePathValue(outcome)}
                  </dd>
                  <small>{outcome.status === 'AVAILABLE' ? recordDate(outcome.measuredAt) : ''}</small>
                </dl>
              ))}
            </div>
          )}

          <footer className={styles.operatingFooter}>
            <span>{state.records.length > 0 ? `저장 기록 ${state.records.length}건` : '저장 기록 없음'}</span>
            {state.authenticated ? (
              <button type="button" onClick={state.record} disabled={state.recording}>
                {state.recording ? '저장 중…' : '현재 판단 기록'}
              </button>
            ) : (
              <span>로그인 후 판단 기록 가능</span>
            )}
          </footer>
        </>
      )}
    </section>
  )
}
