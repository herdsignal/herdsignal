/**
 * StockDetail.jsx — 종목 상세 페이지 (/stock/:ticker)
 *
 * 구성:
 *   1) 브레드크럼 + 종목 헤더 (배지 + 포트폴리오/관심종목 추가 버튼)
 *   2) 2컬럼 그리드 (좌: 메인 / 우: 340px 사이드)
 *   좌: HERD 카드 → 지표 분해 카드 → 재무 정보 → 뉴스
 *   우: 애널리스트 목표가 → 내부자 거래
 *
 * API: getStockHerd(ticker), addToPortfolio(ticker), addToWatchlist(ticker)
 * 래퍼런스: wireframes/wireframe-detail.html
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate }            from 'react-router-dom'
import { getStockHerd, addToPortfolio, addToWatchlist } from '../../api/herdApi'
import HerdDots    from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import styles      from './StockDetail.module.css'

/* 환경변수에서 API 호스트 추출 — 에러 메시지 표시용 */
const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

/* ── 지표 정의 ─────────────────────────────── */
/* min/max: 바 너비 정규화 기준. ma200Deviation은 ±50% 기준 */
const INDICATORS = [
  { key: 'weeklyRsi',      label: '주봉 RSI',      min: 0,   max: 100, unit: '',  signed: false },
  { key: 'monthlyRsi',     label: '월봉 RSI',      min: 0,   max: 100, unit: '',  signed: false },
  { key: 'position52w',    label: '52주 위치',     min: 0,   max: 100, unit: '%', signed: false },
  { key: 'ma200Deviation', label: 'MA200 이격도',  min: -50, max: 50,  unit: '%', signed: true  },
  { key: 'volumeStrength', label: '거래량 강도',   min: 0,   max: 100, unit: '',  signed: false },
]

/* 재무 정보 레이아웃 (데이터 없음 → — 표시) */
const FINANCE_ITEMS = [
  { label: '시가총액',   sub: null },
  { label: 'P/E Ratio',  sub: '업종 평균' },
  { label: '영업이익률', sub: '전년 동기' },
  { label: 'EPS (TTM)',  sub: null },
  { label: '매출 (TTM)', sub: 'YoY' },
  { label: '배당수익률', sub: null },
]

/* ── 유틸 ─────────────────────────────────── */

/** herdStage 정규화: "Herd Scatter" → "scatter" */
function normalizeStage(stage) {
  const s = (stage || '').toLowerCase()
  return s.startsWith('herd ') ? s.slice(5) : s
}

/** 단계 → CSS 변수 색상 */
function stageColor(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return 'var(--rush)'
    case 'drift':   return 'var(--drift)'
    case 'scatter': return 'var(--scatter)'
    case 'flee':    return 'var(--flee)'
    default:        return 'var(--calm)'
  }
}

/** signal → 배지 배경/텍스트 색 */
function signalStyle(signal) {
  switch (signal) {
    case 'SELL':   return { bg: 'rgba(239,68,68,0.1)',   color: 'var(--rush)' }
    case 'REDUCE': return { bg: 'rgba(249,115,22,0.1)',  color: 'var(--drift)' }
    case 'HOLD':   return { bg: 'rgba(113,113,122,0.1)', color: 'var(--calm)' }
    case 'ADD':    return { bg: 'rgba(96,165,250,0.1)',  color: 'var(--scatter)' }
    case 'BUY':    return { bg: 'rgba(59,130,246,0.12)', color: 'var(--flee)' }
    default:       return { bg: 'rgba(113,113,122,0.1)', color: 'var(--calm)' }
  }
}

/** stage → 티커 배지 배경/텍스트 색 */
function badgeColors(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return { background: 'rgba(239,68,68,0.12)',   color: 'var(--rush)' }
    case 'drift':   return { background: 'rgba(249,115,22,0.12)',  color: 'var(--drift)' }
    case 'scatter': return { background: 'rgba(96,165,250,0.12)',  color: 'var(--scatter)' }
    case 'flee':    return { background: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:        return { background: 'rgba(113,113,122,0.12)', color: 'var(--calm)' }
  }
}

/** score → Timing Signal 텍스트 */
function getTimingSignal(score) {
  if (score >= 75) return '보유량의 30% 익절을 고려하세요'
  if (score >= 60) return '보유량의 5% 부분 익절 구간입니다'
  if (score >= 40) return '현재 비중을 유지하세요'
  if (score >= 15) return '분할 매수를 시작할 수 있는 구간입니다'
  return '적극적 추가매수 구간입니다'
}

/** 지표 값 → 바 너비 % (0~100, min~max 범위 정규화) */
function normalizeBar(value, min, max) {
  return Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
}

/** 지표 값 → 표시 문자열 */
function formatIndicator(value, unit, signed) {
  const fixed = value.toFixed(1)
  return signed && value > 0 ? `+${fixed}${unit}` : `${fixed}${unit}`
}

/* ── 버튼 레이블 매핑 ─────────────────────── */
const BTN_LABELS = {
  portfolio: {
    idle:    '포트폴리오 추가',
    loading: '추가 중…',
    added:   '추가됨 ✓',
    exists:  '이미 추가됨',
  },
  watchlist: {
    idle:    '관심종목 추가',
    loading: '추가 중…',
    added:   '추가됨 ✓',
    exists:  '이미 추가됨',
  },
}

/* ── 컴포넌트 ─────────────────────────────── */

export default function StockDetail() {
  const { ticker } = useParams()
  const navigate   = useNavigate()

  /* 상태 */
  const [herdData,         setHerdData]         = useState(null)
  const [loading,          setLoading]           = useState(true)
  const [error,            setError]             = useState(null)
  const [portfolioStatus,  setPortfolioStatus]   = useState('idle')
  const [watchlistStatus,  setWatchlistStatus]   = useState('idle')

  /* HERD 데이터 조회 */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res  = await getStockHerd(ticker.toUpperCase())
      const data = res.data?.data
      if (data) {
        setHerdData(data)
      } else {
        setError(
          `${ticker} 종목의 HERD 데이터가 없습니다.\nPython 스케줄러를 먼저 실행해주세요.`
        )
      }
    } catch {
      setError(`백엔드 서버에 연결할 수 없습니다.\n${API_HOST}이 실행 중인지 확인해주세요.`)
    } finally {
      setLoading(false)
    }
  }, [ticker])

  useEffect(() => { fetchData() }, [fetchData])

  /* 포트폴리오 추가 */
  async function handleAddPortfolio() {
    if (portfolioStatus !== 'idle') return
    setPortfolioStatus('loading')
    try {
      await addToPortfolio(ticker.toUpperCase())
      setPortfolioStatus('added')
    } catch (e) {
      setPortfolioStatus(e.response?.status === 409 ? 'exists' : 'idle')
    }
  }

  /* 관심종목 추가 */
  async function handleAddWatchlist() {
    if (watchlistStatus !== 'idle') return
    setWatchlistStatus('loading')
    try {
      await addToWatchlist(ticker.toUpperCase())
      setWatchlistStatus('added')
    } catch (e) {
      setWatchlistStatus(e.response?.status === 409 ? 'exists' : 'idle')
    }
  }

  /* HERD 데이터에서 사용할 변수들 */
  const herdScore  = herdData?.herdScore ?? 50
  const herdStage  = herdData?.herdStage ?? 'Calm'
  /* 표시용 stage 이름: "Herd Scatter" → "Herd Scatter" (이미 올바른 형태) */
  const stageDisp  = herdStage.startsWith('Herd ') ? herdStage : `Herd ${herdStage}`
  const color      = stageColor(herdStage)
  const sigStyle   = signalStyle(herdData?.signal)

  return (
    <div>

      {/* ── 브레드크럼 ── */}
      <div className={styles.breadcrumb}>
        <span className={styles.breadcrumbLink} onClick={() => navigate('/')}>
          포트폴리오
        </span>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{ticker.toUpperCase()}</span>
      </div>

      {/* ── 종목 헤더 ── */}
      <div className={styles.stockHeader}>
        <div className={styles.stockHeaderLeft}>
          {/* 티커 배지 (로드 전에는 회색) */}
          <div
            className={styles.stockLogo}
            style={herdData ? badgeColors(herdStage) : undefined}
          >
            {ticker.length <= 4 ? ticker.toUpperCase() : ticker.slice(0, 4).toUpperCase()}
          </div>
          <div>
            <div className={styles.stockTicker}>{ticker.toUpperCase()}</div>
            <div className={styles.stockFullname}>미국 주식 · NASDAQ</div>
          </div>
        </div>

        <div className={styles.stockHeaderRight}>
          <button
            className={styles.btnWatchlist}
            onClick={handleAddWatchlist}
            disabled={watchlistStatus === 'loading'}
          >
            {BTN_LABELS.watchlist[watchlistStatus]}
          </button>
          <button
            className={styles.btnPrimary}
            onClick={handleAddPortfolio}
            disabled={portfolioStatus === 'loading'}
          >
            {BTN_LABELS.portfolio[portfolioStatus]}
          </button>
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
          {error.split('\n').map((line, i) => (
            <p key={i} className={i === 0 ? styles.errorTitle : styles.errorSub}>
              {line}
            </p>
          ))}
          <button className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
        </div>
      )}

      {/* ── 2컬럼 컨텐츠 그리드 ── */}
      {!loading && !error && herdData && (
        <div className={styles.contentGrid}>

          {/* ─── 왼쪽 메인 ─── */}
          <div className={styles.colMain}>

            {/* HERD 카드 */}
            <div className={styles.herdCard}>

              {/* 좌: 점수 + 시그널 */}
              <div className={styles.herdScoreSide}>
                <div className={styles.herdEyebrow}>HERD Index</div>
                <div className={styles.herdBigScore} style={{ color }}>
                  {Math.round(herdScore)}
                </div>
                <div className={styles.herdBigStage} style={{ color }}>
                  {stageDisp}
                </div>
                {/* Timing Signal 배지 */}
                <div
                  className={styles.timingSignal}
                  style={{ background: sigStyle.bg, color: sigStyle.color }}
                >
                  {getTimingSignal(herdScore)}
                </div>
              </div>

              {/* 우: HerdDots + 스펙트럼 */}
              <div className={styles.herdAnimSide}>
                <HerdDots score={herdScore} fill dotCount={55} />
                {/* 하단 고정: SpectrumBar + 5단계 라벨 */}
                <div className={styles.herdAnimBottom}>
                  <SpectrumBar score={herdScore} height={3} />
                  <div className={styles.spectrumLabels}>
                    <span>Flee</span>
                    <span>Scatter</span>
                    <span>Calm</span>
                    <span>Drift</span>
                    <span>Rush</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 지표 분해 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>지표 분해</div>
                <div className={styles.cardMeta}>
                  {herdData.scoreDate} 기준
                </div>
              </div>
              <div className={styles.cardBody}>
                {INDICATORS.map((ind) => {
                  const raw  = herdData[ind.key] ?? 0
                  const pct  = normalizeBar(raw, ind.min, ind.max)
                  const disp = formatIndicator(raw, ind.unit, ind.signed)
                  return (
                    <div key={ind.key} className={styles.indicatorRow}>
                      <div className={styles.indicatorLabel}>{ind.label}</div>
                      <div className={styles.indicatorTrack}>
                        <div
                          className={styles.indicatorFill}
                          style={{ width: `${pct}%`, background: color }}
                        />
                      </div>
                      <div className={styles.indicatorValue}>{disp}</div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* 재무 정보 카드 (레이아웃 확보, yfinance 연동 예정) */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>재무 정보</div>
              </div>
              <div className={styles.cardBody}>
                <div className={styles.financeGrid}>
                  {FINANCE_ITEMS.map((item) => (
                    <div key={item.label} className={styles.financeItem}>
                      <div className={styles.financeLabel}>{item.label}</div>
                      <div className={styles.financeValue}>—</div>
                      {item.sub && (
                        <div className={styles.financeSub}>{item.sub} —</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 뉴스 카드 (Finnhub API 연동 예정) */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>최근 뉴스</div>
              </div>
              <div className={styles.cardBodySmall}>
                <p className={styles.placeholderText}>뉴스 연동 예정 (Finnhub API)</p>
              </div>
            </div>
          </div>

          {/* ─── 오른쪽 사이드 ─── */}
          <div className={styles.colSide}>

            {/* 애널리스트 목표가 (레이아웃 확보) */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>애널리스트 목표가</div>
              </div>
              <div className={styles.cardBodySmall}>
                <p className={styles.placeholderText}>데이터 연동 예정</p>
              </div>
            </div>

            {/* 내부자 거래 (레이아웃 확보) */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>내부자 거래</div>
              </div>
              <div className={styles.cardBodySmall}>
                <p className={styles.placeholderText}>데이터 연동 예정</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
