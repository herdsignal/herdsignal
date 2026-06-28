/**
 * Dashboard.jsx — 포트폴리오 대시보드 (/)
 *
 * 구성:
 *   1) 페이지 헤더 (날짜 + 제목 + 종목 추가 버튼)
 *   2) S&P500 HERD 배너 (SPY HERD 점수 + 무리 애니메이션 + 통계)
 *   3) 보유 종목 테이블 (HERD 점수 + 시그널)
 *   4) 빈 상태 UI
 *
 * API: getPortfolioHerd() + getStockHerd('SPY') — 병렬 호출
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate }   from 'react-router-dom'
import { getPortfolioHerd, getStockHerd } from '../../api/herdApi'
import HerdDots          from '../../components/HerdDots/HerdDots'
import SpectrumBar       from '../../components/SpectrumBar/SpectrumBar'
import styles            from './Dashboard.module.css'

/* ── 유틸 ─────────────────────────────────── */

/**
 * herdStage 소문자 정규화
 * API 응답: "Herd Scatter", "Herd Rush" 등 "Herd " 접두사 포함
 * → 접두사 제거 후 소문자: "scatter", "rush"
 */
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

/** stage → 티커 배지 배경/텍스트 색 (HERD 단계 기반) */
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

export default function Dashboard() {
  const navigate = useNavigate()

  /* 상태 */
  const [portfolio, setPortfolio] = useState([])   // 포트폴리오 HERD 목록
  const [spyData,   setSpyData]   = useState(null)  // SPY HERD 데이터
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* 포트폴리오 + SPY 병렬 호출 */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [portfolioRes, spyRes] = await Promise.allSettled([
        getPortfolioHerd(),
        getStockHerd('SPY'),
      ])

      if (portfolioRes.status === 'fulfilled') {
        const responseData = portfolioRes.value.data?.data
        /* API 응답 구조: { stocks: [...], averageScore, totalCount }
           또는 단순 배열 — 두 형태 모두 처리 */
        const stocks = responseData?.stocks
          ?? (Array.isArray(responseData) ? responseData : [])
        setPortfolio(stocks)
      } else {
        /* API 연결 실패 시 빈 목록 + 에러 메시지 */
        setPortfolio([])
        if (!spyRes || spyRes.status === 'rejected') {
          setError('백엔드 서버에 연결할 수 없습니다. localhost:8080이 실행 중인지 확인해주세요.')
        }
      }

      if (spyRes.status === 'fulfilled') {
        setSpyData(spyRes.value.data?.data ?? null)
      }
      /* SPY 실패는 배너에서 — 으로 처리하므로 에러 표시 안 함 */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  /* SPY 점수 (DB에 SPY 없으면 기본값 50 / Calm) */
  const spyScore = spyData?.herdScore ?? 50
  const spyStage = spyData?.herdStage ?? 'Calm'

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

      {/* ── S&P500 HERD 배너 ── */}
      <div className={styles.marketBanner}>

        {/* 좌: 점수 블록 */}
        <div className={styles.bannerScoreBlock}>
          <div className={styles.bannerEyebrow}>S&amp;P 500 HERD Index</div>
          <div
            className={styles.bannerScore}
            style={{ color: stageColor(spyStage) }}
          >
            {spyData ? Math.round(spyScore) : '—'}
          </div>
          <div
            className={styles.bannerStage}
            style={{ color: stageColor(spyStage) }}
          >
            {/* spyStage가 "Calm"이면 "Herd Calm", "Herd Drift"이면 그대로 */}
            {spyStage.startsWith('Herd ') ? spyStage : `Herd ${spyStage}`}
          </div>
          <div className={styles.bannerDesc}>{stageDesc(spyStage)}</div>
        </div>

        {/* 중: 무리 애니메이션 */}
        <div className={styles.bannerAnimBlock}>
          {/* canvas가 position:absolute로 블록 전체를 채움 */}
          <HerdDots score={spyScore} fill dotCount={60} />

          {/* ← Flee / Rush → 라벨 */}
          <div className={styles.bannerAnimLabel}>
            <span>← Flee (매수)</span>
            <span>Rush (익절) →</span>
          </div>

          {/* 하단 스펙트럼 바 */}
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
          <button className={styles.retryBtn} onClick={fetchData}>
            다시 시도
          </button>
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
            {/* 테이블 헤더 */}
            <div className={styles.tableHeader}>
              <div className={styles.th} />
              <div className={styles.th}>종목</div>
              <div className={styles.th}>HERD</div>
              <div className={`${styles.th} ${styles.thRight}`}>시그널</div>
              <div className={styles.th} />
            </div>

            {/* 종목 행 */}
            {portfolio.map((item) => {
              const color  = stageColor(item.herdStage)
              const badge  = badgeStyle(item.herdStage)
              const signal = signalStyle(item.signal)

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
                      style={{ background: color }}
                    />
                  </div>

                  {/* 티커 블록 */}
                  <div className={styles.rowTickerBlock}>
                    <div
                      className={styles.tickerBadge}
                      style={{ background: badge.bg, color: badge.color }}
                    >
                      {/* 4자 초과 티커는 앞 4자만 표시 */}
                      {item.ticker.length <= 4 ? item.ticker : item.ticker.slice(0, 4)}
                    </div>
                    <div>
                      <div className={styles.rowTicker}>{item.ticker}</div>
                      {/* herdStage: "Herd Scatter" 형태 — 그대로 표시 */}
                      <div className={styles.rowName}>{item.herdStage}</div>
                    </div>
                  </div>

                  {/* HERD 열 (점수 + 미니 애니메이션 + 스펙트럼 바) */}
                  <div className={styles.rowHerd}>
                    <div className={styles.rowHerdTop}>
                      <div>
                        <div
                          className={styles.herdNum}
                          style={{ color }}
                        >
                          {Math.round(item.herdScore)}
                        </div>
                        <div className={styles.herdStageName}>
                          {/* "Herd Scatter" → "Scatter" 만 표시 (공간 절약) */}
                          {item.herdStage.startsWith('Herd ')
                            ? item.herdStage.slice(5)
                            : item.herdStage}
                        </div>
                      </div>

                      {/* 미니 HerdDots — fill 모드로 rowAnimWrap을 채움 */}
                      <div className={styles.rowAnimWrap}>
                        <HerdDots
                          score={item.herdScore}
                          fill
                          dotCount={14}
                        />
                      </div>
                    </div>

                    {/* 미니 스펙트럼 바 */}
                    <div className={styles.rowHerdBottom}>
                      <SpectrumBar score={item.herdScore} height={2} />
                    </div>
                  </div>

                  {/* 시그널 배지 */}
                  <div className={styles.signalCell}>
                    <span
                      className={styles.signalBadge}
                      style={{
                        background: signal.bg,
                        color:      signal.color,
                      }}
                    >
                      {item.signal}
                    </span>
                  </div>

                  {/* 이동 화살표 */}
                  <div className={styles.rowAction}>→</div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* ── 빈 상태 UI ── */}
      {!loading && !error && portfolio.length === 0 && (
        <div className={styles.emptyState}>
          <p className={styles.emptyTitle}>아직 종목이 없습니다.</p>
          <p className={styles.emptyDesc}>종목을 추가해보세요.</p>
          <button
            className={styles.btnPrimary}
            onClick={() => navigate('/search')}
          >
            종목 추가
          </button>
        </div>
      )}
    </div>
  )
}
