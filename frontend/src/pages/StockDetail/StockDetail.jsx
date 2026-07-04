/**
 * StockDetail.jsx — 종목 상세 페이지 (/stock/:ticker)
 *
 * 구성:
 *   1) 브레드크럼 + 종목 헤더 (배지 + 포트폴리오/관심종목 추가 버튼)
 *   2) HERD 카드 → Action Layer → HERD 히스토리 → 지표 분해 → 재무 정보
 *
 * API: getStockHerd(ticker), addToPortfolio(ticker), addToWatchlist(ticker)
 * 래퍼런스: wireframes/wireframe-detail.html
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate }                    from 'react-router-dom'
import {
  getStockHerd, addToPortfolio, addToWatchlist, getStockFinancials,
  getStockHerdHistory,
  getPortfolio, getPortfolioSummary,
} from '../../api/herdApi'
import HerdDots    from '../../components/HerdDots/HerdDots'
import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import { buildDecision } from '../../utils/decision'
import styles      from './StockDetail.module.css'

/* 환경변수에서 API 호스트 추출 — 에러 메시지 표시용 */
const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

/*
 * ── HERD v3 지표 정의 (가중치 순) ─────────────
 *
 * weight: HERD 점수 산출 시 반영 비율 (%)
 * min/max: 바 너비 정규화 기준. ma200Deviation은 ±50% 기준
 */
const INDICATORS = [
  { key: 'monthlyRsi',     label: '월봉 RSI',       weight: 24, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'ma200Weekly',    label: '200주 MA 위치',  weight: 20, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'weeklyRsi',      label: '주봉 RSI',       weight: 19, min: 0,   max: 100, unit: '',  signed: false },
  { key: 'position52w',    label: '52주 위치',      weight: 19, min: 0,   max: 100, unit: '%', signed: false },
  { key: 'ma200Deviation', label: 'MA200 이격도',   weight: 18, min: -50, max: 50,  unit: '%', signed: true  },
]

/* ── 재무정보 포맷 함수 ──────────────────────── */

/** 시가총액·매출 → "$X.XXT / $X.XXB / $X.XXM" */
function fmtCap(v) {
  if (v == null) return '—'
  const n = Number(v)
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9)  return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6)  return `$${(n / 1e6).toFixed(2)}M`
  return `$${n.toLocaleString('en-US')}`
}

/** PER → 소수점 1자리 */
function fmtNum1(v) {
  if (v == null) return '—'
  return Number(v).toFixed(1)
}

/** 영업이익률 → "+X.X%" / "-X.X%" */
function fmtPct1(v) {
  if (v == null) return '—'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

/** EPS → "$X.XX" (음수 허용) */
function fmtDollar2(v) {
  if (v == null) return '—'
  const n = Number(v)
  return `${n < 0 ? '-$' : '$'}${Math.abs(n).toFixed(2)}`
}

/** 배당수익률 → "X.XX%" */
function fmtPct2(v) {
  if (v == null) return '—'
  return `${Number(v).toFixed(2)}%`
}

/* 재무 정보 항목 정의 — key: API 응답 camelCase 키, fmt: 포맷 함수 */
const FINANCE_ITEMS = [
  { key: 'marketCap',       label: '시가총액',   sub: null,   fmt: fmtCap     },
  { key: 'trailingPe',      label: 'P/E Ratio',  sub: null,   fmt: fmtNum1    },
  { key: 'operatingMargin', label: '영업이익률', sub: null,   fmt: fmtPct1    },
  { key: 'eps',             label: 'EPS (TTM)',  sub: null,   fmt: fmtDollar2 },
  { key: 'totalRevenue',    label: '매출 (TTM)', sub: null,   fmt: fmtCap     },
  { key: 'dividendYield',   label: '배당수익률', sub: null,   fmt: fmtPct2    },
]

const HISTORY_PERIODS = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '1y', label: '1Y' },
  { value: '3y', label: '3Y' },
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

function formatMultiplier(value) {
  if (value == null) return '×1.00'
  return `×${Number(value).toFixed(2)}`
}

function epsMultiplierDesc(value) {
  const n = Number(value ?? 1)
  if (n <= 0.85) return '4연속 beat'
  if (n <= 0.90) return '3연속 beat'
  if (n <= 0.95) return '2연속 beat'
  if (n >= 1.15) return '4연속 miss'
  if (n >= 1.10) return '3연속 miss'
  if (n >= 1.05) return '2연속 miss'
  return '중립'
}

function sectorMultiplierDesc(value) {
  const n = Number(value ?? 1)
  if (n <= 0.90) return '섹터 대비 강한 우위'
  if (n <= 0.95) return '섹터 대비 우위'
  if (n >= 1.10) return '섹터 대비 뚜렷한 약세'
  if (n >= 1.05) return '섹터 약세'
  return '중립'
}

function qualityTone(level) {
  switch (level) {
    case 'HIGH': return 'var(--flee)'
    case 'GOOD': return 'var(--calm)'
    case 'LIMITED': return 'var(--drift)'
    case 'LOW': return 'var(--rush)'
    default: return 'var(--text-3)'
  }
}

function shouldShowQuality(data) {
  if (!data?.qualityLabel) return false
  if (data.qualityLevel === 'LIMITED' || data.qualityLevel === 'LOW') return true
  return Number(data.qualityScore ?? 100) < 70
}

function qualityWarningText(data) {
  const label = data?.qualityLevel === 'LOW' ? '데이터 부족' : '데이터 제한'
  return `${label}${data?.qualityScore != null ? ` · ${data.qualityScore}점` : ''}`
}

function formatActionScore(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `강도 ${Math.round(n)}`
}

function formatActionRatio(value) {
  const n = Number(value ?? 0)
  if (n <= 0) return '관찰'
  return `${Math.round(n * 100)}%`
}

function formatActionMeta(data) {
  return [
    data?.actionModelVersion ?? 'HERD_v5',
    formatActionScore(data?.actionScore),
  ].filter(Boolean).join(' · ')
}

function actionTone(grade, signal) {
  if (grade === 'STRONG_ACTION') return signal === 'SELL' ? 'var(--rush)' : 'var(--flee)'
  if (grade === 'ACTION') return signal === 'SELL' ? 'var(--drift)' : 'var(--scatter)'
  if (grade === 'WATCH') return 'var(--calm)'
  return 'var(--text-3)'
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
  const [financials,       setFinancials]        = useState(null)
  const [herdHistory,      setHerdHistory]       = useState([])
  const [historyPeriod,    setHistoryPeriod]     = useState('1y')
  const [historyLoading,   setHistoryLoading]    = useState(false)
  const [portfolio,        setPortfolio]         = useState([])
  const [portfolioSummary, setPortfolioSummary]  = useState(null)

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

  /* 포트폴리오 컨텍스트 — 장기투자 판단 패널용. 실패해도 상세 화면은 유지. */
  useEffect(() => {
    Promise.allSettled([getPortfolio(), getPortfolioSummary()])
      .then(([portfolioRes, summaryRes]) => {
        if (portfolioRes.status === 'fulfilled') {
          const data = portfolioRes.value.data?.data
          setPortfolio(Array.isArray(data) ? data : [])
        }
        if (summaryRes.status === 'fulfilled') {
          setPortfolioSummary(summaryRes.value.data?.data ?? null)
        }
      })
  }, [])

  /*
   * 재무정보 — HERD 로딩과 독립적으로 실행.
   * ProcessBuilder 경유로 3~10초 소요될 수 있으므로 별도 effect로 분리.
   * 성공 전까지 FINANCE_ITEMS는 "—"로 표시됨.
   */
  useEffect(() => {
    setFinancials(null)
    getStockFinancials(ticker.toUpperCase())
      .then((res) => { setFinancials(res.data?.data ?? null) })
      .catch(() => { /* 재무정보 실패 시 "—" 유지 */ })
  }, [ticker])

  /* HERD 히스토리 — ticker 또는 기간 변경 시 재조회 */
  useEffect(() => {
    setHistoryLoading(true)
    setHerdHistory([])
    getStockHerdHistory(ticker.toUpperCase(), historyPeriod)
      .then((res) => { setHerdHistory(res.data?.data?.points ?? []) })
      .catch(() => { setHerdHistory([]) })
      .finally(() => { setHistoryLoading(false) })
  }, [ticker, historyPeriod])

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
  const herdScore  = herdData?.herdV4 ?? herdData?.herdScore ?? 50
  const herdStage  = herdData?.herdStage ?? 'Calm'
  /* 표시용 stage 이름: "Herd Scatter" → "Herd Scatter" (이미 올바른 형태) */
  const stageDisp  = herdStage.startsWith('Herd ') ? herdStage : `Herd ${herdStage}`
  const color      = stageColor(herdStage)
  const sigStyle   = signalStyle(herdData?.signal)
  const qualityColor = qualityTone(herdData?.qualityLevel)
  const actionColor = actionTone(herdData?.actionGrade, herdData?.signal)
  const holding    = portfolio.find((item) => item.ticker === ticker.toUpperCase()) ?? null
  const decision   = useMemo(() => buildDecision({
    herdData: { ...herdData, ticker: ticker.toUpperCase() },
    financials,
    holding,
    summary: portfolioSummary,
  }), [herdData, financials, holding, portfolioSummary, ticker])
  const historyPoints = useMemo(() => {
    if (herdHistory.length > 0) return herdHistory
    if (!herdData?.scoreDate) return []
    return [{ date: herdData.scoreDate, score: herdScore }]
  }, [herdHistory, herdData, herdScore])

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

      {/* ── 핵심 컨텐츠 ── */}
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
                {shouldShowQuality(herdData) && (
                  <div
                    className={styles.qualityPill}
                    style={{ color: qualityColor, borderColor: qualityColor }}
                  >
                    {qualityWarningText(herdData)}
                  </div>
                )}
              </div>

              {/* 우: HerdDots + 스펙트럼 */}
              <div className={styles.herdAnimSide}>
                <HerdDots score={herdScore} fill dotCount={55} />
                {/* 하단 고정: SpectrumBar + 5단계 라벨 */}
                <div className={styles.herdAnimBottom}>
                  <SpectrumBar score={herdScore} height={3} />
                  <div className={styles.spectrumLabels}>
                    <span>Flee 군중 이탈</span>
                    <span>Scatter 군중 흩어짐</span>
                    <span>Calm 군중 균형</span>
                    <span>Drift 군중 쏠림</span>
                    <span>Rush 군중 밀집</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Layer 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>Action Layer</div>
                <div className={styles.cardMeta}>{formatActionMeta(herdData)}</div>
              </div>
              <div className={styles.cardBody}>
                <div className={styles.decisionHero}>
                  <div>
                    <div className={styles.decisionLabel}>타이밍 액션</div>
                    <div className={styles.decisionTitle}>
                      {herdData.actionLabel ?? decision.title}
                    </div>
                    <div className={styles.decisionSubtitle}>
                      {herdData.actionRegimeLabel ?? decision.subtitle}
                    </div>
                  </div>
                  <div className={styles.decisionPill} style={{ color: actionColor, borderColor: actionColor }}>
                    {formatActionRatio(herdData.actionRatio)}
                  </div>
                </div>
                <div className={styles.decisionList}>
                  {(herdData.actionReasons?.length ? herdData.actionReasons : decision.notes).slice(0, 2).map((note) => (
                    <div key={note} className={styles.decisionItem}>{note}</div>
                  ))}
                </div>
                {Array.isArray(herdData.actionWarnings) && herdData.actionWarnings.length > 0 && (
                  <div className={styles.actionWarningList}>
                    {herdData.actionWarnings.slice(0, 1).map((warning) => (
                      <span key={warning}>{warning}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* HERD 히스토리 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>HERD Index History</div>
                  <div className={styles.cardMeta}>저장된 HERD 점수 흐름</div>
                </div>
                <div className={styles.historyTabs}>
                  {HISTORY_PERIODS.map((p) => (
                    <button
                      key={p.value}
                      className={`${styles.historyTab} ${historyPeriod === p.value ? styles.historyTabActive : ''}`}
                      onClick={() => setHistoryPeriod(p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className={styles.cardBody}>
                {historyLoading ? (
                  <div className={styles.chartEmpty}>로딩 중…</div>
                ) : (
                  <HerdHistoryChart
                    points={historyPoints}
                    currentScore={herdScore}
                    height={230}
                  />
                )}
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
                  /*
                   * API 응답에 없는 필드는 undefined → null로 처리.
                   */
                  const raw    = herdData[ind.key] ?? null
                  const hasVal = raw != null
                  const pct    = hasVal ? normalizeBar(raw, ind.min, ind.max) : 0
                  const disp   = raw != null ? formatIndicator(raw, ind.unit, ind.signed) : '—'

                  return (
                    <div
                      key={ind.key}
                      className={styles.indicatorRow}
                    >
                      {/* 지표명 */}
                      <div className={styles.indicatorLabel}>{ind.label}</div>

                      {/* 가중치 — 비활성 항목은 "비활성" 텍스트 */}
                      <div className={styles.indicatorWeight}>
                        {ind.weight}%
                      </div>

                      {/* 프로그레스 바 — 값 없으면 빈 트랙만 */}
                      <div className={styles.indicatorTrack}>
                        {hasVal && (
                          <div
                            className={styles.indicatorFill}
                            style={{ width: `${pct}%`, background: color }}
                          />
                        )}
                      </div>

                      {/* 수치 */}
                      <div className={styles.indicatorValue}>{disp}</div>
                    </div>
                  )
                })}
                <div className={styles.adjustmentBox}>
                  <div className={styles.adjustmentRow}>
                    <span>EPS 보정</span>
                    <strong>
                      {formatMultiplier(herdData.epsMultiplier)}
                      <em>{epsMultiplierDesc(herdData.epsMultiplier)}</em>
                    </strong>
                  </div>
                  <div className={styles.adjustmentRow}>
                    <span>섹터 강도 보정</span>
                    <strong>
                      {formatMultiplier(herdData.sectorMultiplier)}
                      <em>{sectorMultiplierDesc(herdData.sectorMultiplier)}</em>
                    </strong>
                  </div>
                </div>
              </div>
            </div>

            {/* 재무 정보 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>재무 정보</div>
                <div className={styles.cardMeta}>
                  {financials ? 'yfinance · 15분 지연' : '로딩 중…'}
                </div>
              </div>
              <div className={styles.cardBody}>
                <div className={styles.financeGrid}>
                  {FINANCE_ITEMS.map((item) => (
                    <div key={item.key} className={styles.financeItem}>
                      <div className={styles.financeLabel}>{item.label}</div>
                      <div className={styles.financeValue}>
                        {item.fmt(financials ? financials[item.key] : null)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  )
}
