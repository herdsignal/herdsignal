/**
 * Dashboard.jsx — 포트폴리오 대시보드 (/)
 *
 * 구성:
 *   1) 페이지 헤더
 *   2) 포트폴리오 평가금액 요약 카드 (총액·수익률·오늘 등락)  ← 신규
 *   3) S&P500 HERD 배너
 *   4) 보유 종목 테이블 (HERD + 평단가·현재가·수익률·평가금액)  ← 확장
 *   5) 빈 상태 UI
 *
 * 데이터 소스:
 *   - getPortfolio()        → 종목 목록 + avgPrice/quantity (항상 동작)
 *   - getPortfolioSummary() → 총액 집계 + 종목별 현재가      (항상 동작)
 *   - getPortfolioHerd()    → HERD 점수 (backend 미구현 시 빈 결과)
 *   - getStockHerd('SPY')   → SPY 배너용 HERD
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getPortfolio,
  getPortfolioSummary,
  getPortfolioHerd,
  getStockHerd,
} from '../../api/herdApi'
import HerdDots          from '../../components/HerdDots/HerdDots'
import SpectrumBar       from '../../components/SpectrumBar/SpectrumBar'
import AvgPriceModal     from '../../components/AvgPriceModal/AvgPriceModal'
import styles            from './Dashboard.module.css'

const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

/* ── 유틸 ─────────────────────────────────── */

/** "Herd Scatter" → "scatter" */
function normalizeStage(stage) {
  const s = (stage || '').toLowerCase()
  return s.startsWith('herd ') ? s.slice(5) : s
}

/** stage → CSS 변수 색상 */
function stageColor(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return 'var(--rush)'
    case 'drift':   return 'var(--drift)'
    case 'scatter': return 'var(--scatter)'
    case 'flee':    return 'var(--flee)'
    default:        return 'var(--calm)'
  }
}

/** stage → 한국어 설명 */
function stageDesc(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return '군중 과열 · 익절 구간'
    case 'drift':   return '군중 유입 · 익절 고려'
    case 'scatter': return '관심 분산 · 추가매수 고려'
    case 'flee':    return '공포 · 매수 구간'
    default:        return '중립 · 보유 유지'
  }
}

/** signal → 배지 스타일 */
function signalStyle(signal) {
  switch (signal) {
    case 'SELL':   return { bg: 'rgba(239,68,68,0.1)',    color: 'var(--rush)' }
    case 'REDUCE': return { bg: 'rgba(249,115,22,0.1)',   color: 'var(--drift)' }
    case 'HOLD':   return { bg: 'rgba(113,113,122,0.1)',  color: 'var(--calm)' }
    case 'ADD':    return { bg: 'rgba(96,165,250,0.1)',   color: 'var(--scatter)' }
    case 'BUY':    return { bg: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:       return { bg: 'rgba(113,113,122,0.1)',  color: 'var(--calm)' }
  }
}

/** stage → 티커 배지 스타일 */
function badgeStyle(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return { bg: 'rgba(239,68,68,0.12)',   color: 'var(--rush)' }
    case 'drift':   return { bg: 'rgba(249,115,22,0.12)',  color: 'var(--drift)' }
    case 'scatter': return { bg: 'rgba(96,165,250,0.12)',  color: 'var(--scatter)' }
    case 'flee':    return { bg: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:        return { bg: 'rgba(113,113,122,0.12)', color: 'var(--calm)' }
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return isNaN(d) ? dateStr : d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

/** USD 금액 포맷: $1,234.56 */
function fmtUSD(value) {
  if (value == null) return '—'
  return `$${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** 퍼센트 포맷: +12.34% / -3.98% */
function fmtPct(value) {
  if (value == null) return '—'
  const n = Number(value)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

/**
 * 수익률 색상
 * 양수 → 초록(#22C55E), 음수 → 빨강(--rush), 0 → 회색
 */
function pctColor(value) {
  if (value == null) return 'var(--text-3)'
  const n = Number(value)
  if (n > 0)  return '#22C55E'
  if (n < 0)  return 'var(--rush)'
  return 'var(--text-3)'
}

/* ── 컴포넌트 ─────────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate()

  /* 포트폴리오 목록 (ticker + avgPrice + quantity) */
  const [portfolio,  setPortfolio]  = useState([])
  /* 포트폴리오 평가금액 요약 (총액 집계 + 종목별 현재가) */
  const [summary,    setSummary]    = useState(null)
  /* HERD 점수 맵 (ticker → {herdScore, herdStage, signal}) — 미구현 시 빈 객체 */
  const [herdMap,    setHerdMap]    = useState({})
  /* SPY HERD 배너 */
  const [spyData,    setSpyData]    = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  /* 평단가 입력 모달 — 대상 ticker (null이면 닫힘) */
  const [modalTicker, setModalTicker] = useState(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* 모든 데이터 병렬 조회 */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [portfolioRes, summaryRes, herdRes, spyRes] = await Promise.allSettled([
        getPortfolio(),         // 종목 목록 (항상 동작)
        getPortfolioSummary(),  // 재무 집계 + 현재가
        getPortfolioHerd(),     // HERD 점수 (미구현 시 404)
        getStockHerd('SPY'),    // SPY 배너
      ])

      /* 포트폴리오 목록 */
      if (portfolioRes.status === 'fulfilled') {
        const raw = portfolioRes.value.data?.data
        setPortfolio(Array.isArray(raw) ? raw : [])
      } else {
        setPortfolio([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
      }

      /* 포트폴리오 재무 요약 */
      if (summaryRes.status === 'fulfilled') {
        setSummary(summaryRes.value.data?.data ?? null)
      }

      /* HERD 점수 (404 실패 정상 — backend 미구현) */
      const map = {}
      if (herdRes.status === 'fulfilled') {
        const herdStocks = herdRes.value?.data?.data?.stocks ?? []
        herdStocks.forEach((h) => { map[h.ticker] = h })
      }
      setHerdMap(map)

      /* SPY 배너 — 응답 구조 디버깅 로그 (확인 후 제거 예정) */
      console.log('[SPY] status:', spyRes.status)
      if (spyRes.status === 'fulfilled') {
        const inner = spyRes.value.data?.data ?? null
        console.log('[SPY] 파싱 결과:', inner)
        setSpyData(inner)
      } else {
        console.error('[SPY] 요청 실패:', spyRes.reason?.message, spyRes.reason)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  /* ticker → 현재가 데이터 맵 (getPortfolioSummary 결과) */
  const priceMap = useMemo(() => {
    const map = {}
    summary?.stocks?.forEach((s) => { map[s.ticker] = s })
    return map
  }, [summary])

  const spyScore = spyData?.herdScore ?? 50
  const spyStage = spyData?.herdStage ?? 'Calm'

  /* 모달 저장 완료 → 데이터 재조회 후 닫기 */
  const handleModalSaved = useCallback(async () => {
    setModalTicker(null)
    await fetchData()
  }, [fetchData])

  /* 찾고 있는 티커 종목의 modalTicker 정보 */
  const modalStock = portfolio.find((p) => p.ticker === modalTicker)

  return (
    <div>

      {/* ── 페이지 헤더 ── */}
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>포트폴리오</h1>
        </div>
        <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
          종목 추가
        </button>
      </div>

      {/* ── 포트폴리오 평가금액 요약 카드 ── */}
      {summary && (
        <div className={styles.summarySection}>
          <div className={styles.summaryCard}>
            <div className={styles.summaryLabel}>총 평가금액</div>
            <div className={styles.summaryValue}>{fmtUSD(summary.totalValue)}</div>
            <div className={styles.summarySub}>
              매입 {fmtUSD(summary.totalCost)}
            </div>
          </div>
          <div className={styles.summaryCard}>
            <div className={styles.summaryLabel}>총 수익률</div>
            <div
              className={styles.summaryValue}
              style={{ color: pctColor(summary.totalReturnPct) }}
            >
              {fmtPct(summary.totalReturnPct)}
            </div>
            <div className={styles.summarySub}>
              {summary.totalReturnPct >= 0 ? '평가이익' : '평가손실'}
            </div>
          </div>
          <div className={styles.summaryCard}>
            <div className={styles.summaryLabel}>오늘 등락</div>
            <div
              className={styles.summaryValue}
              style={{ color: pctColor(summary.dailyChangePct) }}
            >
              {fmtPct(summary.dailyChangePct)}
            </div>
            <div className={styles.summarySub}>전일 대비</div>
          </div>
        </div>
      )}

      {/* ── S&P500 HERD 배너 ── */}
      <div className={styles.marketBanner}>

        {/* 좌: 점수 블록 */}
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

        {/* 중: 무리 애니메이션 */}
        <div className={styles.bannerAnimBlock}>
          <HerdDots score={spyScore} fill dotCount={60} />
          <div className={styles.bannerAnimLabel}>
            <span>← Flee (매수)</span>
            <span>Rush (익절) →</span>
          </div>
          <div className={styles.bannerSpectrumOverlay}>
            <SpectrumBar score={spyScore} height={3} />
          </div>
        </div>

        {/* 우: 통계 */}
        <div className={styles.bannerStatsBlock}>
          <div className={styles.bannerStatItem}>
            <div className={styles.bannerStatLabel}>SPY 종가</div>
            <div className={styles.bannerStatValue}>—</div>
          </div>
          <div className={styles.bannerStatItem}>
            <div className={styles.bannerStatLabel}>1개월 수익률</div>
            <div className={styles.bannerStatValue}>—</div>
          </div>
          <div className={styles.bannerStatItem}>
            <div className={styles.bannerStatLabel}>업데이트</div>
            <div className={styles.bannerStatUpdate}>
              {spyData ? formatDate(spyData.scoreDate) : '—'}
            </div>
          </div>
        </div>
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

      {/* ── 종목 테이블 ── */}
      {!loading && !error && portfolio.length > 0 && (
        <>
          <div className={styles.sectionRow}>
            <div className={styles.sectionTitle}>
              보유 종목 · {portfolio.length}
            </div>
          </div>

          <div className={styles.stockTable}>
            {/* 헤더 — 순서: 종목 → 재무정보(평단가·현재가·수익률·평가금액) → HERD → 시그널 */}
            <div className={styles.tableHeader}>
              <div className={styles.th} />
              <div className={styles.th}>종목</div>
              <div className={`${styles.th} ${styles.thRight}`}>평단가</div>
              <div className={`${styles.th} ${styles.thRight}`}>현재가</div>
              <div className={`${styles.th} ${styles.thRight}`}>수익률</div>
              <div className={`${styles.th} ${styles.thRight}`}>평가금액</div>
              <div className={styles.th}>HERD</div>
              <div className={styles.th}>시그널</div>
              <div className={styles.th} />
              <div className={styles.th} />
            </div>

            {/* 종목 행 */}
            {portfolio.map((item) => {
              /* HERD 데이터 (optional) */
              const herd   = herdMap[item.ticker]
              const stage  = herd?.herdStage ?? 'Calm'
              const color  = stageColor(stage)
              const badge  = badgeStyle(stage)
              const signal = signalStyle(herd?.signal)

              /* 재무 데이터 (summary map) */
              const price = priceMap[item.ticker]

              /* avgPrice는 포트폴리오 엔티티에서 직접 사용 */
              const hasAvgPrice = item.avgPrice != null && item.quantity != null

              return (
                <div
                  key={item.ticker}
                  className={styles.tableRow}
                  onClick={() => navigate(`/stock/${item.ticker}`)}
                >
                  {/* 컬러 스트라이프 */}
                  <div className={styles.rowStripeWrap}>
                    <div
                      className={styles.rowStripe}
                      style={{ background: hasAvgPrice ? color : 'var(--border2)' }}
                    />
                  </div>

                  {/* 티커 블록 */}
                  <div className={styles.rowTickerBlock}>
                    <div
                      className={styles.tickerBadge}
                      style={{ background: badge.bg, color: badge.color }}
                    >
                      {item.ticker.length <= 4 ? item.ticker : item.ticker.slice(0, 4)}
                    </div>
                    <div>
                      <div className={styles.rowTicker}>{item.ticker}</div>
                      <div className={styles.rowName}>{stage}</div>
                    </div>
                  </div>

                  {/* 평단가 */}
                  <div className={styles.priceCell}>
                    {hasAvgPrice
                      ? fmtUSD(item.avgPrice)
                      : <span className={styles.dashCell}>—</span>}
                  </div>

                  {/* 현재가 + 일일 등락폭 (2줄 표시) */}
                  <div className={styles.priceCell}>
                    {price ? (
                      <div className={styles.priceCellDouble}>
                        <div>{fmtUSD(price.currentPrice)}</div>
                        <div
                          className={styles.priceSubText}
                          style={{ color: pctColor(price.dailyChangePct) }}
                        >
                          {fmtPct(price.dailyChangePct)}
                        </div>
                      </div>
                    ) : (
                      <span className={styles.dashCell}>—</span>
                    )}
                  </div>

                  {/* 수익률 */}
                  <div className={styles.priceCell}>
                    {price ? (
                      <span style={{ color: pctColor(price.returnPct) }}>
                        {fmtPct(price.returnPct)}
                      </span>
                    ) : (
                      <span className={styles.dashCell}>—</span>
                    )}
                  </div>

                  {/* 평가금액 */}
                  <div className={styles.priceCell}>
                    {price
                      ? fmtUSD(price.marketValue)
                      : <span className={styles.dashCell}>—</span>}
                  </div>

                  {/* HERD 열 — 재무정보 뒤에 배치 */}
                  <div className={styles.rowHerd}>
                    {herd ? (
                      <>
                        <div className={styles.rowHerdTop}>
                          <div>
                            <div className={styles.herdNum} style={{ color }}>
                              {Math.round(herd.herdScore)}
                            </div>
                            <div className={styles.herdStageName}>
                              {stage.startsWith('Herd ') ? stage.slice(5) : stage}
                            </div>
                          </div>
                          <div className={styles.rowAnimWrap}>
                            <HerdDots score={herd.herdScore} fill dotCount={14} />
                          </div>
                        </div>
                        <div className={styles.rowHerdBottom}>
                          <SpectrumBar score={herd.herdScore} height={2} />
                        </div>
                      </>
                    ) : (
                      /* HERD 점수 미구현 시 — dashCell과 동일 스타일 */
                      <div className={styles.rowHerdEmpty}>—</div>
                    )}
                  </div>

                  {/* 시그널 배지 */}
                  <div className={styles.signalCell}>
                    {herd ? (
                      <span
                        className={styles.signalBadge}
                        style={{ background: signal.bg, color: signal.color }}
                      >
                        {herd.signal}
                      </span>
                    ) : (
                      <span className={styles.dashCell}>—</span>
                    )}
                  </div>

                  {/* 평단가 입력/수정 버튼 */}
                  <div className={styles.avgPriceBtnCell}>
                    <button
                      className={hasAvgPrice ? styles.editBtn : styles.inputBtn}
                      onClick={(e) => {
                        e.stopPropagation()  /* 행 클릭(상세 이동) 방지 */
                        setModalTicker(item.ticker)
                      }}
                    >
                      {hasAvgPrice ? '수정' : '입력'}
                    </button>
                  </div>

                  {/* 이동 화살표 */}
                  <div className={styles.rowAction}>→</div>
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

      {/* ── 평단가 입력 모달 ── */}
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
