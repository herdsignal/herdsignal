/**
 * Watchlist.jsx — 관심 종목 페이지 (/watchlist)
 *
 * Dashboard 구조 재사용. 주요 차이점:
 *   - API: getWatchlistHerd() (Portfolio 대신)
 *   - 카드: 평단가/수익률 섹션 없이 HERD 점수 + 시그널 + 삭제만
 *   - 삭제: removeFromWatchlist(ticker) → 성공 시 로컬 상태에서 즉시 제거
 *   - 빈 상태: "관심 종목이 없습니다" + 종목 검색 버튼
 *
 * API: getWatchlistHerd() + getStockHerd('SPY') — 병렬 호출
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate }   from 'react-router-dom'
import { getWatchlistHerd, getStockHerd, removeFromWatchlist } from '../../api/herdApi'
import HerdDots  from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import styles    from './Watchlist.module.css'

/* 환경변수에서 API 호스트 추출 — 에러 메시지 표시용 */
const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

/* ── 유틸 (Dashboard와 동일) ──────────────── */

/** herdStage 소문자 정규화: "Herd Scatter" → "scatter" */
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

/** signal → 배지 배경색 + 텍스트 색 */
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

/** stage → 티커 배지 배경/텍스트 색 */
function badgeStyle(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return { bg: 'rgba(239,68,68,0.12)',   color: 'var(--rush)' }
    case 'drift':   return { bg: 'rgba(249,115,22,0.12)',  color: 'var(--drift)' }
    case 'scatter': return { bg: 'rgba(96,165,250,0.12)',  color: 'var(--scatter)' }
    case 'flee':    return { bg: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:        return { bg: 'rgba(113,113,122,0.12)', color: 'var(--calm)' }
  }
}

/** scoreDate → 한국어 날짜 문자열 */
function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (isNaN(d)) return dateStr
  return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

/* ── 컴포넌트 ─────────────────────────────── */

export default function Watchlist() {
  const navigate = useNavigate()

  const [watchlist,      setWatchlist]      = useState([])
  const [spyData,        setSpyData]        = useState(null)
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  /* 삭제 중인 ticker — 중복 요청 방지 */
  const [deletingTicker, setDeletingTicker] = useState(null)
  /* SPY 데이터 ref 캐시 — Dashboard와 동일한 StrictMode 대응 */
  const spyDataCache = useRef(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* 관심 종목 조회 (SPY와 분리) */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const watchlistRes = await getWatchlistHerd().catch(() => null)

      if (watchlistRes) {
        const responseData = watchlistRes.data?.data
        /* API 응답: { stocks: [...], averageScore, totalCount } 또는 배열 */
        const stocks = responseData?.stocks
          ?? (Array.isArray(responseData) ? responseData : [])
        setWatchlist(stocks)
      } else {
        setWatchlist([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  /*
   * SPY 배너 — Dashboard와 동일한 구조.
   * ref 캐시로 StrictMode 이중 실행 시 state 재설정 문제 방지.
   */
  useEffect(() => {
    if (spyDataCache.current) {
      setSpyData(spyDataCache.current)
      return
    }
    getStockHerd('SPY')
      .then((res) => {
        const data = res.data?.data ?? null
        spyDataCache.current = data
        setSpyData(data)
      })
      .catch(() => { /* SPY 실패 시 배너 기본값(Calm/50) 유지 */ })
  }, [])

  /* 관심 종목 삭제 — API 성공 시 로컬 상태 즉시 제거 */
  async function handleDelete(e, ticker) {
    e.stopPropagation()
    if (deletingTicker) return
    setDeletingTicker(ticker)
    try {
      await removeFromWatchlist(ticker)
      setWatchlist(prev => prev.filter(item => item.ticker !== ticker))
    } catch {
      /* 삭제 실패 — 목록 그대로 유지 */
    } finally {
      setDeletingTicker(null)
    }
  }

  const spyScore = spyData?.herdScore ?? 50
  const spyStage = spyData?.herdStage ?? 'Calm'

  return (
    <div>

      {/* ── 페이지 헤더 ── */}
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>관심 종목</h1>
        </div>
        <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
          종목 추가
        </button>
      </div>

      {/* ── S&P500 HERD 배너 (Dashboard와 동일) ── */}
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

      {/* ── 로딩 상태 ── */}
      {loading && (
        <div className={styles.loadingState}>
          <span className={styles.loadingText}>로딩 중…</span>
        </div>
      )}

      {/* ── 에러 상태 ── */}
      {!loading && error && (
        <div className={styles.errorState}>
          <p className={styles.errorText}>{error}</p>
          <button className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
        </div>
      )}

      {/* ── 관심 종목 카드 그리드 — 2열 ── */}
      {!loading && !error && watchlist.length > 0 && (
        <>
          <div className={styles.sectionRow}>
            <div className={styles.sectionTitle}>관심 종목 · {watchlist.length}</div>
          </div>

          <div className={styles.stockGrid}>
            {watchlist.map((item) => {
              const color      = stageColor(item.herdStage)
              const badge      = badgeStyle(item.herdStage)
              const signal     = signalStyle(item.signal)
              const stageName  = item.herdStage.startsWith('Herd ')
                ? item.herdStage.slice(5)
                : item.herdStage
              const isDeleting = deletingTicker === item.ticker

              return (
                <div
                  key={item.ticker}
                  className={styles.stockCard}
                  onClick={() => navigate(`/stock/${item.ticker}`)}
                  style={{ opacity: isDeleting ? 0.4 : 1 }}
                >
                  {/* 좌측 HERD 단계 컬러 스트라이프 */}
                  <div className={styles.cardStripe} style={{ background: color }} />

                  {/* 삭제 버튼 — 우상단, hover 시 표시 */}
                  <button
                    className={styles.cardDeleteBtn}
                    onClick={e => handleDelete(e, item.ticker)}
                    disabled={!!deletingTicker}
                    title={`${item.ticker} 관심 종목에서 삭제`}
                  >
                    {isDeleting ? '…' : '✕'}
                  </button>

                  {/* 카드 상단: 종목 (좌) + HERD (우) */}
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
                      <div className={styles.cardHerdNum} style={{ color }}>
                        {Math.round(item.herdScore)}
                      </div>
                      <div className={styles.cardHerdStage}>{stageName}</div>
                    </div>
                  </div>

                  {/* 카드 하단: 시그널 배지만 (관심 종목은 재무 데이터 없음) */}
                  <div className={styles.cardBottom}>
                    <span
                      className={styles.cardSignalBadge}
                      style={{ background: signal.bg, color: signal.color }}
                    >
                      {item.signal}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* ── 빈 상태 UI ── */}
      {!loading && !error && watchlist.length === 0 && (
        <div className={styles.emptyState}>
          <p className={styles.emptyTitle}>관심 종목이 없습니다.</p>
          <p className={styles.emptyDesc}>종목을 검색해 추가해보세요.</p>
          <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
            종목 검색
          </button>
        </div>
      )}
    </div>
  )
}
