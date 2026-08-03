import styles from './StockDetail.module.css'

const AREA_LABELS = {
  BUSINESS_HEALTH: '기업 체력',
  EXPECTATION_VALUATION: '기대 · 가격',
  MARKET_SECTOR: '시장 · 섹터',
  CHART_CROWD: '차트 · 군중',
  INFORMATION_CHANGE: '정보 변화',
}

const STATUS_LABELS = {
  AVAILABLE: '확인',
  PARTIAL: '일부',
  NO_VIEW: '미연결',
  BLOCKED: '차단',
}

const BUSINESS_FACT_IDS = new Set([
  'BUSINESS.PIT.REVENUE_YOY',
  'BUSINESS.PIT.NET_MARGIN',
  'BUSINESS.PIT.OPERATING_CASH_FLOW_YOY',
  'BUSINESS.PIT.LIABILITIES_TO_ASSETS',
])

function normalized(review) {
  if (!review) return null
  if (review.objective) {
    return {
      status: review.synthesis?.decision ?? review.status,
      headline: review.synthesis?.headline ?? '상태 관찰',
      objective: review.objective,
      mandate: review.mandate,
      portfolioFit: review.portfolioFit,
      veto: review.riskVeto,
      limitations: review.synthesis?.limitations ?? [],
    }
  }
  return {
    status: review.status === 'AVAILABLE' ? 'OBSERVE' : review.status,
    headline: review.status === 'AVAILABLE' ? '상태 관찰' : '데이터 확인 필요',
    objective: review,
    mandate: null,
    portfolioFit: null,
    veto: null,
    limitations: review.dataGate?.reasons ?? [],
  }
}

function pct(value) {
  if (!Number.isFinite(Number(value))) return '—'
  return `${(Number(value) * 100).toFixed(1)}%`
}

function businessFacts(objective) {
  return (objective?.evidencePacket?.facts ?? [])
    .filter((fact) => fact.quality === 'AVAILABLE' && BUSINESS_FACT_IDS.has(fact.id))
    .map((fact) => ({
      ...fact,
      displayValue: pct(fact.value),
    }))
}

function guidanceFacts(objective) {
  return (objective?.evidencePacket?.facts ?? [])
    .filter((fact) => fact.quality === 'AVAILABLE' && fact.id.startsWith('EXPECTATION.GUIDANCE.'))
    .slice(0, 4)
}

export default function StockOperatingReview({ state }) {
  const view = normalized(state.review)
  const verifiedBusinessFacts = businessFacts(view?.objective)
  const verifiedGuidanceFacts = guidanceFacts(view?.objective)

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
                  <dd>{fact.displayValue}</dd>
                </dl>
              ))}
            </div>
          )}


          {verifiedGuidanceFacts.length > 0 && (
            <div className={styles.operatingGuidanceFacts}>
              <div>
                <span>SEC GUIDANCE</span>
                <small>{verifiedGuidanceFacts[0].asOfDate} 접수 · 방향 판정 아님</small>
              </div>
              {verifiedGuidanceFacts.map((fact) => (
                <dl key={fact.id}>
                  <dt>{fact.label}</dt>
                  <dd>{fact.value}</dd>
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
