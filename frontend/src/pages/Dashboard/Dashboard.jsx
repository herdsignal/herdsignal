/**
 * Dashboard.jsx — 포트폴리오 대시보드 (/)
 *
 * 구성:
 *   1) 페이지 헤더
 *   2) 포트폴리오 평가금액 요약 카드 (총액·수익률·오늘 등락)
 *   3) S&P500 HERD 배너 (HerdDots + SpectrumBar 유지)
 *   4) 보유 종목 2열 카드 그리드
 *      카드: 좌 스트라이프 | 종목+HERD | 평가금액+수익률 | 시그널+현재가
 *   5) 빈 상태 UI
 *
 * 데이터 소스:
 *   - getPortfolio()        → 종목 목록 + avgPrice/quantity
 *   - getPortfolioSummary() → 총액 집계 + 종목별 현재가
 *   - getPortfolioHerd()    → HERD 점수 (backend 미구현 시 빈 결과)
 *   - getStockHerd('SPY')   → SPY 배너용 HERD (독립 useEffect)
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getPortfolio,
  getPortfolioSummary,
  getPortfolioHerd,
  getStockHerd,
  removeFromPortfolio,
} from '../../api/herdApi'
import HerdDots      from '../../components/HerdDots/HerdDots'
import SpectrumBar   from '../../components/SpectrumBar/SpectrumBar'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import styles        from './Dashboard.module.css'

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

/** stage → 한국어 설명 (배너 하단) */
function stageDesc(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return '군중 과열 · 익절 구간'
    case 'drift':   return '군중 유입 · 익절 고려'
    case 'scatter': return '관심 분산 · 추가매수 고려'
    case 'flee':    return '공포 · 매수 구간'
    default:        return '중립 · 보유 유지'
  }
}

/** signal → 배지 배경·텍스트 색 */
function signalStyle(signal) {
  switch (signal) {
    case 'SELL':   return { bg: 'rgba(239,68,68,0.1)',    color: '#EF4444' }
    case 'REDUCE': return { bg: 'rgba(249,115,22,0.1)',   color: '#F97316' }
    case 'HOLD':   return { bg: 'rgba(113,113,122,0.14)', color: '#A1A1AA' }
    case 'ADD':    return { bg: 'rgba(96,165,250,0.12)',  color: '#60A5FA' }
    case 'BUY':    return { bg: 'rgba(59,130,246,0.12)',  color: '#3B82F6' }
    default:       return { bg: 'rgba(113,113,122,0.14)', color: '#A1A1AA' }
  }
}

/** stage → 티커 배지 배경·텍스트 색 */
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

/** 수익률 색상: 양수→초록, 음수→빨강, 0→회색 */
function pctColor(value) {
  if (value == null) return 'var(--text-3)'
  const n = Number(value)
  if (n > 0)  return '#22C55E'
  if (n < 0)  return '#EF4444'
  return 'var(--text-3)'
}

/* ── 컴포넌트 ─────────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate()

  const [portfolio,      setPortfolio]      = useState([])
  const [summary,        setSummary]        = useState(null)
  const [herdMap,        setHerdMap]        = useState({})
  const [spyData,        setSpyData]        = useState(null)
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  /* 평단가 입력 모달 대상 ticker */
  const [modalTicker,    setModalTicker]    = useState(null)
  /* 삭제 중인 ticker — 중복 요청 방지 */
  const [deletingTicker, setDeletingTicker] = useState(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* ── 포트폴리오 데이터 병렬 조회 ── */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [portfolioRes, summaryRes, herdRes] = await Promise.allSettled([
        getPortfolio(),
        getPortfolioSummary(),
        getPortfolioHerd(),
      ])

      if (portfolioRes.status === 'fulfilled') {
        const raw = portfolioRes.value.data?.data
        setPortfolio(Array.isArray(raw) ? raw : [])
      } else {
        setPortfolio([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
      }

      if (summaryRes.status === 'fulfilled') {
        setSummary(summaryRes.value.data?.data ?? null)
      }

      const map = {}
      if (herdRes.status === 'fulfilled') {
        const herdStocks = herdRes.value?.data?.data?.stocks ?? []
        herdStocks.forEach((h) => { map[h.ticker] = h })
      }
      setHerdMap(map)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  /*
   * SPY 배너 — 포트폴리오 배치와 완전히 분리.
   * HMR 스테일 클로저 문제 방지를 위해 독립 useEffect로 처리.
   */
  useEffect(() => {
    getStockHerd('SPY')
      .then((res) => {
        const data = res.data?.data ?? null
        setSpyData(data)
      })
      .catch(() => { /* SPY 실패 시 배너 기본값(Calm/50) 유지 */ })
  }, [])

  /* ticker → 현재가 데이터 맵 */
  const priceMap = useMemo(() => {
    const map = {}
    summary?.stocks?.forEach((s) => { map[s.ticker] = s })
    return map
  }, [summary])

  /* 포트폴리오 종목 삭제 — API 성공 시 로컬 상태 즉시 제거 (낙관적 업데이트) */
  async function handleDelete(e, ticker) {
    e.stopPropagation()
    if (deletingTicker) return
    setDeletingTicker(ticker)
    try {
      await removeFromPortfolio(ticker)
      setPortfolio(prev => prev.filter(item => item.ticker !== ticker))
    } catch {
      /* 삭제 실패 — 목록 그대로 유지 */
    } finally {
      setDeletingTicker(null)
    }
  }

  const spyScore = spyData?.herdScore ?? 50
  const spyStage = spyData?.herdStage ?? 'Calm'

  /* 모달 저장 완료 → 데이터 재조회 후 닫기 */
  const handleModalSaved = useCallback(async () => {
    setModalTicker(null)
    await fetchData()
  }, [fetchData])

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
            <div className={styles.summarySub}>매입 {fmtUSD(summary.totalCost)}</div>
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

      {/* ── S&P500 HERD 배너 — HerdDots + SpectrumBar 유지 ── */}
      <div className={styles.marketBanner}>
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

      {/* ── 종목 카드 그리드 — 2열 ── */}
      {!loading && !error && portfolio.length > 0 && (
        <>
          <div className={styles.sectionRow}>
            <div className={styles.sectionTitle}>보유 종목 · {portfolio.length}</div>
          </div>

          <div className={styles.stockGrid}>
            {portfolio.map((item) => {
              const herd      = herdMap[item.ticker]
              const stage     = herd?.herdStage ?? 'Calm'
              const color     = stageColor(stage)
              const badge     = badgeStyle(stage)
              const signal    = signalStyle(herd?.signal)
              /* "Herd Scatter" → "Scatter" */
              const stageName = stage.startsWith('Herd ') ? stage.slice(5) : stage

              const price       = priceMap[item.ticker]
              const hasAvgPrice = item.avgPrice != null && item.quantity != null
              const isDeleting  = deletingTicker === item.ticker

              return (
                <div
                  key={item.ticker}
                  className={styles.stockCard}
                  onClick={() => navigate(`/stock/${item.ticker}`)}
                  style={{ opacity: isDeleting ? 0.4 : 1 }}
                >
                  {/* 좌측 HERD 단계 컬러 스트라이프 */}
                  <div className={styles.cardStripe} style={{ background: color }} />

                  {/* 삭제 버튼 — 우상단 절대 위치, hover 시 표시 */}
                  <button
                    className={styles.cardDeleteBtn}
                    onClick={e => handleDelete(e, item.ticker)}
                    disabled={!!deletingTicker}
                    title={`${item.ticker} 포트폴리오에서 삭제`}
                  >
                    {isDeleting ? '…' : '✕'}
                  </button>

                  {/* 카드 상단: 종목 정보 (좌) + HERD 점수 (우) */}
                  <div className={styles.cardTop}>
                    <div className={styles.cardTickerBlock}>
                      <div
                        className={styles.cardTickerBadge}
                        style={{ background: badge.bg, color: badge.color }}
                      >
                        {item.ticker.length <= 4 ? item.ticker : item.ticker.slice(0, 4)}
                      </div>
                      <div>
                        <div className={styles.cardTicker}>{item.ticker}</div>
                        <div className={styles.cardStageName}>{stageName}</div>
                      </div>
                    </div>

                    <div className={styles.cardHerd}>
                      {herd ? (
                        <>
                          <div className={styles.cardHerdNum} style={{ color }}>
                            {Math.round(herd.herdScore)}
                          </div>
                          <div className={styles.cardHerdStage}>{stageName}</div>
                        </>
                      ) : (
                        <span className={styles.cardDash}>—</span>
                      )}
                    </div>
                  </div>

                  {/*
                   * 카드 중간: 재무 데이터
                   * 평단가 입력 → 평가금액 + 수익률
                   * 미입력 → 안내 텍스트 + 입력 버튼
                   */}
                  <div className={styles.cardMiddle}>
                    {hasAvgPrice ? (
                      <div className={styles.cardFinance}>
                        <div>
                          <div className={styles.cardFinanceLabel}>평가금액</div>
                          <div className={styles.cardFinanceValue}>
                            {price ? fmtUSD(price.marketValue) : '—'}
                          </div>
                        </div>
                        <div className={styles.cardFinanceRight}>
                          <div className={styles.cardFinanceLabel}>수익률</div>
                          <div
                            className={styles.cardFinanceValue}
                            style={{ color: price ? pctColor(price.returnPct) : 'var(--text-3)' }}
                          >
                            {price ? fmtPct(price.returnPct) : '—'}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className={styles.cardNoPrice}>
                        <span className={styles.cardNoPriceText}>
                          평단가를 입력하면 수익률을 확인할 수 있어요
                        </span>
                        <button
                          className={styles.cardInputBtn}
                          onClick={e => {
                            e.stopPropagation()
                            setModalTicker(item.ticker)
                          }}
                        >
                          입력
                        </button>
                      </div>
                    )}
                  </div>

                  {/* 카드 하단: 시그널 배지 (좌) + 현재가·등락 (우, 평단가 있을 때만) */}
                  <div className={styles.cardBottom}>
                    <div>
                      {herd ? (
                        <span
                          className={styles.cardSignalBadge}
                          style={{ background: signal.bg, color: signal.color }}
                        >
                          {herd.signal}
                        </span>
                      ) : (
                        <span className={styles.cardDash}>—</span>
                      )}
                    </div>

                    {hasAvgPrice && price && (
                      <div className={styles.cardPriceInfo}>
                        <span className={styles.cardCurrentPrice}>
                          {fmtUSD(price.currentPrice)}
                        </span>
                        <span
                          className={styles.cardDailyChange}
                          style={{ color: pctColor(price.dailyChangePct) }}
                        >
                          {fmtPct(price.dailyChangePct)}
                        </span>
                      </div>
                    )}
                  </div>
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
