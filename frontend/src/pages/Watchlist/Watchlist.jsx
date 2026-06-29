/**
 * Watchlist.jsx — 관심 종목 페이지 (/watchlist)
 *
 * Dashboard 구조 재사용. 주요 차이점:
 *   - API: getWatchlistHerd() (Portfolio 대신)
 *   - 테이블 행 우측: 시그널 배지 + 삭제 버튼
 *   - 삭제: removeFromWatchlist(ticker) → 성공 시 로컬 상태에서 즉시 제거
 *   - 빈 상태: "관심 종목이 없습니다" + 종목 검색 버튼
 *
 * API: getWatchlistHerd() + getStockHerd('SPY') — 병렬 호출
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate }   from 'react-router-dom'
import { getWatchlistHerd, getStockHerd, removeFromWatchlist } from '../../api/herdApi'
import HerdDots          from '../../components/HerdDots/HerdDots'
import SpectrumBar       from '../../components/SpectrumBar/SpectrumBar'
import styles            from './Watchlist.module.css'

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
    case 'SELL':   return { bg: 'rgba(239,68,68,0.1)',    color: 'var(--rush)' }
    case 'REDUCE': return { bg: 'rgba(249,115,22,0.1)',   color: 'var(--drift)' }
    case 'HOLD':   return { bg: 'rgba(113,113,122,0.1)',  color: 'var(--calm)' }
    case 'ADD':    return { bg: 'rgba(96,165,250,0.1)',   color: 'var(--scatter)' }
    case 'BUY':    return { bg: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:       return { bg: 'rgba(113,113,122,0.1)',  color: 'var(--calm)' }
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

  /* 상태 */
  const [watchlist,      setWatchlist]      = useState([])   // 관심 종목 목록
  const [spyData,        setSpyData]        = useState(null)  // SPY HERD 데이터
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  /* 삭제 중인 티커 (한 번에 하나만 허용) */
  const [deletingTicker, setDeletingTicker] = useState(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* 관심 종목 + SPY 병렬 호출 */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [watchlistRes, spyRes] = await Promise.allSettled([
        getWatchlistHerd(),
        getStockHerd('SPY'),
      ])

      if (watchlistRes.status === 'fulfilled') {
        const responseData = watchlistRes.value.data?.data
        /* API 응답: { stocks: [...], averageScore, totalCount } 또는 배열 */
        const stocks = responseData?.stocks
          ?? (Array.isArray(responseData) ? responseData : [])
        setWatchlist(stocks)
      } else {
        setWatchlist([])
        if (!spyRes || spyRes.status === 'rejected') {
          setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
        }
      }

      if (spyRes.status === 'fulfilled') {
        setSpyData(spyRes.value.data?.data ?? null)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  /* 관심 종목 삭제 */
  async function handleDelete(e, ticker) {
    e.stopPropagation()   /* 행 클릭(상세 페이지 이동) 이벤트 차단 */
    if (deletingTicker) return   /* 삭제 중에는 중복 요청 방지 */
    setDeletingTicker(ticker)
    try {
      await removeFromWatchlist(ticker)
      /* API 성공 시 로컬 상태에서 즉시 제거 (재조회 없음) */
      setWatchlist(prev => prev.filter(item => item.ticker !== ticker))
    } catch {
      /* 삭제 실패 시 목록 그대로 유지 (별도 알림 없음 — MVP) */
    } finally {
      setDeletingTicker(null)
    }
  }

  /* SPY 기본값 */
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

      {/* ── 관심 종목 테이블 ── */}
      {!loading && !error && watchlist.length > 0 && (
        <>
          <div className={styles.sectionRow}>
            <div className={styles.sectionTitle}>
              관심 종목 · {watchlist.length}
            </div>
          </div>

          <div className={styles.stockTable}>
            {/* 테이블 헤더 */}
            <div className={styles.tableHeader}>
              <div className={styles.th} />
              <div className={styles.th}>종목</div>
              <div className={styles.th}>HERD</div>
              <div className={`${styles.th} ${styles.thRight}`}>시그널</div>
              <div className={styles.th} />
            </div>

            {/* 종목 행 */}
            {watchlist.map((item) => {
              const color  = stageColor(item.herdStage)
              const badge  = badgeStyle(item.herdStage)
              const signal = signalStyle(item.signal)
              const isDeleting = deletingTicker === item.ticker

              return (
                <div
                  key={item.ticker}
                  className={styles.tableRow}
                  onClick={() => navigate(`/stock/${item.ticker}`)}
                >
                  {/* 컬러 스트라이프 */}
                  <div className={styles.rowStripeWrap}>
                    <div className={styles.rowStripe} style={{ background: color }} />
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
                      <div className={styles.rowName}>{item.herdStage}</div>
                    </div>
                  </div>

                  {/* HERD 열 */}
                  <div className={styles.rowHerd}>
                    <div className={styles.rowHerdTop}>
                      <div>
                        <div className={styles.herdNum} style={{ color }}>
                          {Math.round(item.herdScore)}
                        </div>
                        <div className={styles.herdStageName}>
                          {item.herdStage.startsWith('Herd ')
                            ? item.herdStage.slice(5)
                            : item.herdStage}
                        </div>
                      </div>
                      <div className={styles.rowAnimWrap}>
                        <HerdDots score={item.herdScore} fill dotCount={14} />
                      </div>
                    </div>
                    <div className={styles.rowHerdBottom}>
                      <SpectrumBar score={item.herdScore} height={2} />
                    </div>
                  </div>

                  {/* 시그널 배지 */}
                  <div className={styles.signalCell}>
                    <span
                      className={styles.signalBadge}
                      style={{ background: signal.bg, color: signal.color }}
                    >
                      {item.signal}
                    </span>
                  </div>

                  {/* 삭제 버튼 (이벤트 버블링 차단) */}
                  <div className={styles.deleteCell} onClick={e => e.stopPropagation()}>
                    <button
                      className={styles.btnDelete}
                      onClick={e => handleDelete(e, item.ticker)}
                      disabled={!!deletingTicker}
                      title={`${item.ticker} 관심 종목에서 삭제`}
                    >
                      {isDeleting ? '…' : '✕'}
                    </button>
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
