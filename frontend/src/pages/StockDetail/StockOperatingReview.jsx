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

const BUSINESS_GROUPS = [
  {
    id: 'growth',
    label: '성장',
    primaryId: 'BUSINESS.PIT.REVENUE_YOY',
    primaryLabel: '매출 전년 대비',
  },
  {
    id: 'profitability',
    label: '수익성',
    primaryId: 'BUSINESS.PIT.NET_MARGIN',
    primaryLabel: '순이익률',
    secondaryId: 'BUSINESS.PIT.NET_MARGIN_YOY_CHANGE',
    secondaryLabel: '전년 대비',
  },
  {
    id: 'cash',
    label: '현금창출',
    primaryId: 'BUSINESS.PIT.OPERATING_CASH_FLOW_YOY',
    primaryLabel: '영업현금흐름 전년 대비',
  },
  {
    id: 'balance',
    label: '재무구조',
    primaryId: 'BUSINESS.PIT.LIABILITIES_TO_ASSETS',
    primaryLabel: '부채/자산',
    secondaryId: 'BUSINESS.PIT.LIABILITIES_TO_ASSETS_YOY_CHANGE',
    secondaryLabel: '전년 대비',
  },
]

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
  const available = new Map(
    (objective?.evidencePacket?.facts ?? [])
      .filter((fact) => fact.quality === 'AVAILABLE')
      .map((fact) => [fact.id, fact]),
  )
  return BUSINESS_GROUPS.flatMap((group) => {
    const primary = available.get(group.primaryId)
    const secondary = available.get(group.secondaryId)
    if (!primary && !secondary) return []
    return [{
      ...group,
      asOfDate: primary?.asOfDate ?? secondary?.asOfDate,
      primaryValue: primary ? pct(primary.value) : '—',
      secondaryValue: secondary ? pct(secondary.value) : null,
    }]
  })
}

function guidanceFacts(objective) {
  return (objective?.evidencePacket?.facts ?? [])
    .filter((fact) => fact.quality === 'AVAILABLE' && fact.id.startsWith('EXPECTATION.GUIDANCE.'))
    .slice(0, 4)
}

const MARKET_FACT_IDS = new Set([
  'MARKET.SPY.RETURN_63',
  'MARKET.SECTOR.RELATIVE_63',
  'MARKET.ATTRIBUTION.CLASS',
])

const ATTRIBUTION_LABELS = {
  MARKET_COMMON: '시장 공통',
  SECTOR_COMMON: '섹터 공통',
  STOCK_SPECIFIC: '종목 고유',
  MIXED: '혼합',
  NO_DOWNSIDE_ATTRIBUTION: '하락 경로 아님',
}

function marketFacts(objective) {
  return (objective?.evidencePacket?.facts ?? [])
    .filter((fact) => fact.quality === 'AVAILABLE' && MARKET_FACT_IDS.has(fact.id))
    .map((fact) => ({
      ...fact,
      displayValue: fact.id === 'MARKET.ATTRIBUTION.CLASS'
        ? ATTRIBUTION_LABELS[fact.value] ?? fact.value
        : pct(fact.value),
    }))
}

function pricePathValue(outcome) {
  if (!outcome || outcome.status === 'UNAVAILABLE') return '자료 없음'
  if (outcome.status === 'PENDING') return '대기'
  const value = Number(outcome.priceReturnPct)
  if (!Number.isFinite(value)) return '자료 없음'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

function recordDate(value) {
  if (!value) return '기준일 없음'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('ko-KR', { year: 'numeric', month: 'numeric', day: 'numeric' })
}

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
                <small>{recordDate(latestRecord.referencePriceDate)} 종가 기준 · 성공 판정 아님</small>
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
