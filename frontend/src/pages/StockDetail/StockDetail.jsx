/**
 * StockDetail.jsx — 종목 상세 페이지 (/stock/:ticker)
 *
 * 구성:
 *   1) 브레드크럼 + 종목 헤더 (배지 + 포트폴리오/관심종목 추가 버튼)
 *   2) 2컬럼 그리드 (좌: 메인 / 우: 340px 사이드)
 *   좌: HERD 카드 → 장기투자 판단 → 지표 분해 카드 → 재무 정보
 *   우: 판단 요약 → 다음 행동
 *
 * API: getStockHerd(ticker), addToPortfolio(ticker), addToWatchlist(ticker)
 * 래퍼런스: wireframes/wireframe-detail.html
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate }                    from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  getStockHerd, addToPortfolio, addToWatchlist, getStockFinancials,
  getStockPrices,
  getPortfolio, getPortfolioSummary,
} from '../../api/herdApi'
import HerdDots    from '../../components/HerdDots/HerdDots'
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

function dataQualityLabel(label) {
  if (!label) return null
  return label.replace('신뢰도', '데이터 품질')
}

const HERD_VALIDATION = [
  { label: '10년 MDD 개선', value: '+7.3%p', desc: 'Buy & Hold 대비 평균 최대낙폭 완화' },
  { label: '수익률 보존', value: '38.8%', desc: '장기 급등 수익 일부를 포기하고 변동성 완화' },
  { label: '검증 성격', value: '보조형', desc: '전량 매매가 아닌 추가매수·일부익절 타이밍 참고' },
]

/** 가격 차트 커스텀 툴팁 */
function PriceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className={styles.priceTooltip}>
      <div className={styles.priceTooltipDate}>{label}</div>
      <div className={styles.priceTooltipVal}>${Number(payload[0]?.value).toFixed(2)}</div>
    </div>
  )
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
  const [pricePoints,      setPricePoints]       = useState([])
  const [priceTab,         setPriceTab]          = useState('1M')
  const [priceLoading,     setPriceLoading]      = useState(false)
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

  /* 가격 차트 — ticker 또는 탭 변경 시 재조회 */
  useEffect(() => {
    setPriceLoading(true)
    setPricePoints([])
    getStockPrices(ticker.toUpperCase(), priceTab)
      .then((res) => { setPricePoints(res.data?.data?.points ?? []) })
      .catch(() => { setPricePoints([]) })
      .finally(() => { setPriceLoading(false) })
  }, [ticker, priceTab])

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
  const holding    = portfolio.find((item) => item.ticker === ticker.toUpperCase()) ?? null
  const decision   = useMemo(() => buildDecision({
    herdData: { ...herdData, ticker: ticker.toUpperCase() },
    financials,
    holding,
    summary: portfolioSummary,
  }), [herdData, financials, holding, portfolioSummary, ticker])
  const sideFacts = useMemo(() => {
    const facts = [
      {
        label: 'HERD 상태',
        value: `${Math.round(herdScore)} · ${stageDisp}`,
        tone: color,
      },
      {
        label: '추천 행동',
        value: decision.title,
        tone: color,
      },
      {
        label: '데이터 품질',
        value: herdData?.qualityLabel
          ? `${dataQualityLabel(herdData.qualityLabel)} · ${herdData.qualityScore}점`
          : '산출 대기',
        tone: qualityColor,
      },
      {
        label: '보유 상태',
        value: holding
          ? `${Number(holding.quantity ?? 0).toLocaleString('ko-KR')}주 보유`
          : '포트폴리오 미보유',
        tone: 'var(--text-1)',
      },
    ]

    if (financials?.trailingPe != null) {
      facts.push({
        label: '밸류에이션',
        value: `PER ${fmtNum1(financials.trailingPe)}`,
        tone: 'var(--text-1)',
      })
    }

    return facts
  }, [color, decision.title, financials, herdData, herdScore, holding, qualityColor, stageDisp])

  /* 가격 차트 색상 — 기간 첫날 대비 마지막날 방향 */
  const priceColor = useMemo(() => {
    if (pricePoints.length < 2) return '#3B82F6'
    return pricePoints[pricePoints.length - 1].close >= pricePoints[0].close
      ? '#3B82F6' : '#EF4444'
  }, [pricePoints])

  /* X축 날짜 포맷 — 단기(1M/3M)는 M/D, 장기(1Y/5Y)는 YY.MM */
  const fmtPriceDate = useCallback((dateStr) => {
    const d = new Date(dateStr + 'T00:00:00')
    return (priceTab === '1M' || priceTab === '3M')
      ? `${d.getMonth() + 1}/${d.getDate()}`
      : `${String(d.getFullYear()).slice(2)}.${String(d.getMonth() + 1).padStart(2, '0')}`
  }, [priceTab])

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
                <div
                  className={styles.qualityPill}
                  style={{ color: qualityColor, borderColor: qualityColor }}
                >
                  {dataQualityLabel(herdData.qualityLabel) ?? '데이터 품질 산출 중'}
                  {herdData.qualityScore != null && ` · ${herdData.qualityScore}점`}
                </div>
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

            {/* 장기투자 판단 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>장기투자 판단</div>
                <div className={styles.cardMeta}>HERD + 보유 비중 + 재무 컨텍스트</div>
              </div>
              <div className={styles.cardBody}>
                <div className={styles.decisionHero}>
                  <div>
                    <div className={styles.decisionLabel}>추천 행동</div>
                    <div className={styles.decisionTitle}>{decision.title}</div>
                    <div className={styles.decisionSubtitle}>{decision.subtitle}</div>
                  </div>
                  <div className={styles.decisionPill} style={{ color, borderColor: color }}>
                    {decision.priority}
                  </div>
                </div>
                <div className={styles.decisionList}>
                  {decision.notes.map((note) => (
                    <div key={note} className={styles.decisionItem}>{note}</div>
                  ))}
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
                <div className={styles.qualityBox}>
                  <div className={styles.qualityBoxHead}>
                    <div>
                      <span>데이터 품질</span>
                      <strong style={{ color: qualityColor }}>
                        {dataQualityLabel(herdData.qualityLabel) ?? '산출 대기'}
                      </strong>
                    </div>
                    {herdData.qualityScore != null && (
                      <em>{herdData.qualityScore}/100</em>
                    )}
                  </div>
                  <p>{herdData.qualitySummary ?? '가격 데이터와 지표 완성도를 기준으로 데이터 품질을 계산합니다.'}</p>
                  {Array.isArray(herdData.qualityReasons) && herdData.qualityReasons.length > 0 && (
                    <div className={styles.qualityReasonGrid}>
                      {herdData.qualityReasons.slice(0, 6).map((reason) => (
                        <span key={reason}>{reason}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className={styles.validationBox}>
                  <div className={styles.qualityBoxHead}>
                    <div>
                      <span>HERD 검증 요약</span>
                      <strong>장기 보유 보조형 신호</strong>
                    </div>
                    <em>10년</em>
                  </div>
                  <p>
                    HERD는 Buy & Hold를 대체하기보다 장기 보유 중 군중 이탈·밀집 구간의
                    추가매수와 일부익절 타이밍을 보조합니다.
                  </p>
                  <div className={styles.validationGrid}>
                    {HERD_VALIDATION.map((item) => (
                      <div key={item.label} className={styles.validationItem}>
                        <span>{item.label}</span>
                        <strong>{item.value}</strong>
                        <em>{item.desc}</em>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 가격 차트 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>가격 차트</div>
                <div className={styles.priceTabs}>
                  {['1M', '3M', '1Y', '5Y'].map((p) => (
                    <button
                      key={p}
                      className={`${styles.priceTab} ${priceTab === p ? styles.priceTabActive : ''}`}
                      onClick={() => setPriceTab(p)}
                    >{p}</button>
                  ))}
                </div>
              </div>
              <div className={styles.cardBody}>
                {priceLoading ? (
                  <div className={styles.chartEmpty}>로딩 중…</div>
                ) : pricePoints.length === 0 ? (
                  <div className={styles.chartEmpty}>데이터 없음</div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={pricePoints} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={priceColor} stopOpacity={0.25} />
                          <stop offset="100%" stopColor={priceColor} stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <XAxis
                        dataKey="date"
                        tickFormatter={fmtPriceDate}
                        interval="preserveStartEnd"
                        tick={{ fontSize: 10, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                        axisLine={false}
                        tickLine={false}
                        tickMargin={6}
                      />
                      <YAxis
                        domain={['auto', 'auto']}
                        tick={{ fontSize: 10, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                        axisLine={false}
                        tickLine={false}
                        width={44}
                        tickFormatter={(v) => `$${v.toFixed(0)}`}
                      />
                      <Tooltip content={<PriceTooltip />} />
                      <Area
                        type="monotone"
                        dataKey="close"
                        stroke={priceColor}
                        strokeWidth={1.5}
                        fill="url(#priceGrad)"
                        dot={false}
                        activeDot={{ r: 3, fill: priceColor, strokeWidth: 0 }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
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

          {/* ─── 오른쪽 사이드 ─── */}
          <div className={styles.colSide}>

            {/* 판단 요약 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>판단 요약</div>
                <div className={styles.cardMeta}>장기투자 기준</div>
              </div>
              <div className={styles.cardBodySmall}>
                <div className={styles.sideFactList}>
                  {sideFacts.map((fact) => (
                    <div key={fact.label} className={styles.sideFact}>
                      <span>{fact.label}</span>
                      <strong style={{ color: fact.tone }}>{fact.value}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 다음 행동 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>다음 행동</div>
                <div className={styles.cardMeta}>과잉 매매 방지</div>
              </div>
              <div className={styles.cardBodySmall}>
                <div className={styles.actionNoteList}>
                  <p>{decision.subtitle}</p>
                  {decision.notes.slice(0, 3).map((note) => (
                    <span key={note}>{note}</span>
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
