/**
 * StockDetail.jsx — 종목 상세 페이지 (/stock/:ticker)
 *
 * 구성:
 *   1) 브레드크럼 + 종목 헤더 (배지 + 포트폴리오/관심종목 추가 버튼)
 *   2) HERD 카드 → Action Layer → 신호 근거/지표 → 신뢰도 → 히스토리 → 재무 가드 → 판단 기록
 *
 * API: getStockHerd(ticker), getStockFinancials(ticker), addToPortfolio(ticker), addToWatchlist(ticker)
 * 래퍼런스: wireframes/wireframe-detail.html
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate }                    from 'react-router-dom'
import {
  getStockHerd, addToPortfolio, addToWatchlist,
  getStockFinancials, getStockHerdHistory, getStockHerdReliability,
  getPortfolio, getPortfolioSummary,
  getSignalJournal, createSignalJournal, deleteSignalJournal,
} from '../../api/herdApi'
import HerdDots    from '../../components/HerdDots/HerdDots'
import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import StockAvatar from '../../components/StockAvatar/StockAvatar'
import SignalJournalModal from '../../components/SignalJournalModal/SignalJournalModal'
import { buildDecision } from '../../utils/decision'
import { qualityColor, qualityReasonText, qualityWarningText, shouldShowQuality } from '../../utils/dataQuality'
import { getHerdMomentum } from '../../utils/herdMomentum'
import { formatSignalAgeLabel, formatSignalDurationDetail } from '../../utils/signalDuration'
import {
  formatJournalAmount,
  formatJournalPrice,
  formatJournalProfit,
  formatJournalQuantity,
  formatJournalTime,
  formatJournalCount,
  summarizeSignalJournal,
} from '../../utils/signalJournal'
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

function formatActionBasis(data) {
  const ratio = Number(data?.actionRatio ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return '현재 비중 유지'

  const pct = Math.round(ratio * 100)
  if (data?.signal === 'BUY' || data?.signal === 'ADD') {
    return `목표 투자금 기준 ${pct}% 분할 투입`
  }
  if (data?.signal === 'SELL' || data?.signal === 'REDUCE') {
    return `보유 평가금액 기준 ${pct}% 축소`
  }
  return '현재 비중 유지'
}

function formatActionMeta(data) {
  return [
    data?.actionModelVersion ?? 'HERD_v5',
    formatActionScore(data?.actionScore),
  ].filter(Boolean).join(' · ')
}

function fmtReliabilityScore(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${Math.round(n)}/100`
}

function sampleQualityLabel(value) {
  switch (value) {
    case 'HIGH': return '충분'
    case 'MEDIUM': return '보통'
    case 'LOW': return '부족'
    default: return '—'
  }
}

function signalEdgeLabel(value) {
  switch (value) {
    case 'POSITIVE': return '우위'
    case 'NEUTRAL': return '중립'
    case 'NEGATIVE': return '약함'
    case 'INSUFFICIENT': return '표본 부족'
    default: return '—'
  }
}

function signalEdgeTone(value) {
  switch (value) {
    case 'POSITIVE': return 'buy'
    case 'NEGATIVE': return 'sell'
    default: return 'neutral'
  }
}

function actionTone(grade, signal) {
  if (grade === 'STRONG_ACTION') return signal === 'SELL' ? 'var(--rush)' : 'var(--flee)'
  if (grade === 'ACTION') return signal === 'SELL' ? 'var(--drift)' : 'var(--scatter)'
  if (grade === 'WATCH') return 'var(--calm)'
  return 'var(--text-3)'
}

function evidenceTone(type) {
  switch (type) {
    case 'buy': return 'var(--flee)'
    case 'sell': return 'var(--rush)'
    case 'warning': return 'var(--drift)'
    default: return 'var(--calm)'
  }
}

function buildSignalEvidence(data) {
  if (!data) return []

  const items = []
  const push = (label, value, caption, type = 'neutral') => {
    if (value == null) return
    if (typeof value !== 'string' && Number.isNaN(Number(value))) return
    items.push({
      label,
      value: typeof value === 'string' ? value : Math.round(Number(value)),
      caption,
      type,
    })
  }

  const monthlyRsi = Number(data.monthlyRsi)
  const weeklyRsi = Number(data.weeklyRsi)
  const position52w = Number(data.position52w)
  const ma200Weekly = Number(data.ma200Weekly)
  const ma200Deviation = Number(data.ma200Deviation)
  const epsMultiplier = Number(data.epsMultiplier ?? 1)
  const sectorMultiplier = Number(data.sectorMultiplier ?? 1)

  if (monthlyRsi <= 30) push('월봉 RSI', monthlyRsi, '장기 심리 하단', 'buy')
  else if (monthlyRsi >= 70) push('월봉 RSI', monthlyRsi, '장기 심리 상단', 'sell')

  if (weeklyRsi <= 30) push('주봉 RSI', weeklyRsi, '중기 과매도권', 'buy')
  else if (weeklyRsi >= 70) push('주봉 RSI', weeklyRsi, '중기 과열권', 'sell')

  if (position52w <= 30) push('52주 위치', `${position52w.toFixed(1)}%`, '연중 하단권', 'buy')
  else if (position52w >= 70) push('52주 위치', `${position52w.toFixed(1)}%`, '연중 상단권', 'sell')

  if (ma200Weekly <= 30) push('200주 MA', ma200Weekly, '장기 추세 하단', 'buy')
  else if (ma200Weekly >= 70) push('200주 MA', ma200Weekly, '장기 추세 상단', 'sell')

  if (ma200Deviation <= 30) push('MA200 이격', ma200Deviation, '장기선 대비 눌림', 'buy')
  else if (ma200Deviation >= 70) push('MA200 이격', ma200Deviation, '장기선 대비 과열', 'sell')

  if (epsMultiplier < 1) {
    items.push({
      label: 'EPS 보정',
      value: formatMultiplier(epsMultiplier),
      caption: epsMultiplierDesc(epsMultiplier),
      type: 'buy',
    })
  } else if (epsMultiplier > 1) {
    items.push({
      label: 'EPS 보정',
      value: formatMultiplier(epsMultiplier),
      caption: epsMultiplierDesc(epsMultiplier),
      type: 'warning',
    })
  }

  if (sectorMultiplier < 1) {
    items.push({
      label: '섹터 강도',
      value: formatMultiplier(sectorMultiplier),
      caption: sectorMultiplierDesc(sectorMultiplier),
      type: 'buy',
    })
  } else if (sectorMultiplier > 1) {
    items.push({
      label: '섹터 강도',
      value: formatMultiplier(sectorMultiplier),
      caption: sectorMultiplierDesc(sectorMultiplier),
      type: 'warning',
    })
  }

  if (items.length === 0) {
    items.push({
      label: 'HERD 균형',
      value: Math.round(data.herdV4 ?? data.herdScore ?? 50),
      caption: '강한 쏠림 없음',
      type: 'neutral',
    })
  }

  return items.slice(0, 5)
}

function reliabilityTone(grade) {
  switch (grade) {
    case 'STRONG': return 'var(--flee)'
    case 'GOOD': return 'var(--scatter)'
    case 'WATCH': return 'var(--drift)'
    case 'DATA_LIMITED': return 'var(--text-3)'
    default: return 'var(--calm)'
  }
}

function fmtReliabilityPct(value, suffix = '%') {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}${suffix}`
}

function fmtReliabilityPlainPct(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toFixed(0)}%`
}

function fmtAnnualActions(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toFixed(1)}회`
}

function fmtCurrencyCompact(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  if (Math.abs(n) >= 1_000_000_000_000) return `$${(n / 1_000_000_000_000).toFixed(1)}T`
  if (Math.abs(n) >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  return `$${Math.round(n).toLocaleString()}`
}

function fmtNumber(value, digits = 1) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toFixed(digits)
}

function fmtFinancePct(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toFixed(1)}%`
}

function fundamentalTone(level) {
  switch (level) {
    case 'CLEAR': return 'var(--scatter)'
    case 'CAUTION': return 'var(--drift)'
    case 'RISK': return 'var(--rush)'
    default: return 'var(--text-3)'
  }
}

function evaluateFundamentalGuard(financials, herdData) {
  if (!financials) {
    return {
      level: 'LIMITED',
      label: '재무 데이터 제한',
      summary: '제한된 재무 데이터 기준으로 판단을 보류합니다.',
      reasons: ['핵심 재무 지표를 불러오지 못했습니다.'],
    }
  }

  const eps = Number(financials.eps)
  const pe = Number(financials.trailingPe)
  const margin = Number(financials.operatingMargin)
  const revenue = Number(financials.totalRevenue)
  const marketCap = Number(financials.marketCap)
  const isBuySignal = herdData?.signal === 'BUY' || herdData?.signal === 'ADD'
  const isSellSignal = herdData?.signal === 'SELL' || herdData?.signal === 'REDUCE'
  const risks = []
  const cautions = []

  if (!Number.isFinite(revenue) || revenue <= 0) cautions.push('매출 데이터 확인 필요')
  if (!Number.isFinite(marketCap) || marketCap <= 0) cautions.push('시가총액 데이터 확인 필요')
  if (!Number.isFinite(eps)) cautions.push('EPS 데이터 확인 필요')
  if (Number.isFinite(eps) && eps < 0) cautions.push('EPS 적자')
  if (!Number.isFinite(margin)) cautions.push('영업이익률 데이터 확인 필요')
  if (Number.isFinite(margin) && margin < 0) cautions.push('영업이익률 음수')
  if (Number.isFinite(pe) && pe >= 80) cautions.push('PER 80 이상')
  if (!Number.isFinite(pe) && (!Number.isFinite(eps) || eps <= 0)) cautions.push('PER 산정 불가')

  if (Number.isFinite(eps) && eps < 0 && Number.isFinite(margin) && margin < 0) {
    risks.push('적자와 영업손실 동시 확인')
  }
  if ((!Number.isFinite(revenue) || revenue <= 0) && Number.isFinite(eps) && eps < 0) {
    risks.push('매출 공백과 EPS 적자 동시 확인')
  }
  if (isSellSignal && Number.isFinite(pe) && pe >= 100) {
    risks.push('고PER 구간의 Rush/Drift 신호')
  }

  const level = risks.length > 0 ? 'RISK' : cautions.length > 0 ? 'CAUTION' : 'CLEAR'
  const label = level === 'RISK'
    ? '재무 리스크 큼'
    : level === 'CAUTION'
      ? '재무 확인 필요'
      : '확인된 주요 경고 없음'

  let summary = '제한된 주요 재무 지표에서 큰 경고는 확인되지 않습니다.'
  if (isBuySignal && level === 'CLEAR') {
    summary = '매수 신호를 재무 데이터가 크게 방해하지 않습니다.'
  } else if (isBuySignal && level === 'CAUTION') {
    summary = '매수 신호지만 포지션 크기를 줄여 접근해야 합니다.'
  } else if (isBuySignal && level === 'RISK') {
    summary = '저점 신호만으로 매수 판단하지 마세요.'
  } else if (isSellSignal && level !== 'CLEAR') {
    summary = '익절 신호를 더 보수적으로 볼 구간입니다.'
  } else if (level === 'CAUTION') {
    summary = 'HERD 신호와 별도로 재무 지표 확인이 필요합니다.'
  } else if (level === 'RISK') {
    summary = 'HERD 신호보다 재무 리스크 확인을 우선해야 합니다.'
  }

  return {
    level,
    label,
    summary,
    reasons: [...risks, ...cautions].slice(0, 3),
  }
}

function currentSignalReliability(herdData, reliability) {
  if (!reliability) return null
  const signal = herdData?.signal

  if (signal === 'BUY' || signal === 'ADD') {
    return {
      label: '현재 매수 신호',
      value: reliability.fleeHitRate,
      sample: reliability.fleeSampleSize,
      caption: `매수 edge ${signalEdgeLabel(reliability.buySignalEdge)}`,
    }
  }
  if (signal === 'SELL' || signal === 'REDUCE') {
    return {
      label: '현재 익절 신호',
      value: reliability.rushHitRate,
      sample: reliability.rushSampleSize,
      caption: `익절 edge ${signalEdgeLabel(reliability.sellSignalEdge)}`,
    }
  }
  return {
    label: '종목별 모델 적합도',
    value: reliability.fitScore,
    sample: reliability.totalSignalSamples,
    caption: `표본 품질 ${sampleQualityLabel(reliability.sampleQuality)}`,
    scoreValue: true,
  }
}

function reliabilityEvidenceItems(reliability) {
  if (!reliability) return []
  return [
    {
      label: '매수 후 1M',
      value: fmtReliabilityPct(reliability.buyReturn1m),
      caption: 'Flee/Scatter 평균',
      tone: Number(reliability.buyReturn1m) >= 0 ? 'buy' : 'sell',
    },
    {
      label: '매수 후 3M',
      value: fmtReliabilityPct(reliability.buyReturn3m),
      caption: 'Flee/Scatter 평균',
      tone: Number(reliability.buyReturn3m) >= 0 ? 'buy' : 'sell',
    },
    {
      label: '매수 후 6M',
      value: fmtReliabilityPct(reliability.buyReturn6m),
      caption: 'Flee/Scatter 평균',
      tone: Number(reliability.buyReturn6m) >= 0 ? 'buy' : 'sell',
    },
    {
      label: '익절 후 1M',
      value: fmtReliabilityPct(reliability.sellDrawdown1m),
      caption: 'Drift/Rush 평균 저점',
      tone: Number(reliability.sellDrawdown1m) <= 0 ? 'sell' : 'neutral',
    },
    {
      label: '익절 후 3M',
      value: fmtReliabilityPct(reliability.sellDrawdown3m),
      caption: 'Drift/Rush 평균 저점',
      tone: Number(reliability.sellDrawdown3m) <= 0 ? 'sell' : 'neutral',
    },
    {
      label: '매수 edge',
      value: signalEdgeLabel(reliability.buySignalEdge),
      caption: `${reliability.fleeSampleSize ?? 0}회 표본`,
      tone: signalEdgeTone(reliability.buySignalEdge),
    },
    {
      label: '익절 edge',
      value: signalEdgeLabel(reliability.sellSignalEdge),
      caption: `${reliability.rushSampleSize ?? 0}회 표본`,
      tone: signalEdgeTone(reliability.sellSignalEdge),
    },
  ]
}

function journalActionLabel(type) {
  switch (type) {
    case 'BUY': return '매수 기록'
    case 'HOLD': return '보류 기록'
    case 'SELL': return '익절 기록'
    default: return '판단 기록'
  }
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
  const [herdHistory,      setHerdHistory]       = useState([])
  const [historyPeriod,    setHistoryPeriod]     = useState('1y')
  const [historyLoading,   setHistoryLoading]    = useState(false)
  const [reliability,      setReliability]       = useState(null)
  const [reliabilityLoading, setReliabilityLoading] = useState(false)
  const [financials,       setFinancials]        = useState(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)
  const [portfolio,        setPortfolio]         = useState([])
  const [portfolioSummary, setPortfolioSummary]  = useState(null)
  const [signalLogs,       setSignalLogs]        = useState([])
  const [journalAction,    setJournalAction]     = useState(null)

  const normalizedTicker = ticker.toUpperCase()

  const fetchSignalLogs = useCallback(async () => {
    try {
      const res = await getSignalJournal(normalizedTicker)
      setSignalLogs((res.data?.data ?? []).slice(0, 5))
    } catch {
      setSignalLogs([])
    }
  }, [normalizedTicker])

  useEffect(() => { fetchSignalLogs() }, [fetchSignalLogs])

  /* HERD 데이터 조회 */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res  = await getStockHerd(normalizedTicker)
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
  }, [normalizedTicker, ticker])

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

  /* HERD 히스토리 — ticker 또는 기간 변경 시 재조회 */
  useEffect(() => {
    setHistoryLoading(true)
    setHerdHistory([])
    getStockHerdHistory(normalizedTicker, historyPeriod)
      .then((res) => { setHerdHistory(res.data?.data?.points ?? []) })
      .catch(() => { setHerdHistory([]) })
      .finally(() => { setHistoryLoading(false) })
  }, [normalizedTicker, historyPeriod])

  /* HERD 신호 신뢰도 — 저장된 HERD 히스토리와 가격 데이터 기반 */
  useEffect(() => {
    setReliabilityLoading(true)
    setReliability(null)
    getStockHerdReliability(normalizedTicker, 3)
      .then((res) => { setReliability(res.data?.data ?? null) })
      .catch(() => { setReliability(null) })
      .finally(() => { setReliabilityLoading(false) })
  }, [normalizedTicker])

  /* Fundamental Guard — HERD 판단을 막을 재무 경고만 확인 */
  useEffect(() => {
    setFinancialsLoading(true)
    setFinancials(null)
    getStockFinancials(normalizedTicker)
      .then((res) => { setFinancials(res.data?.data ?? null) })
      .catch(() => { setFinancials(null) })
      .finally(() => { setFinancialsLoading(false) })
  }, [normalizedTicker])

  /* 포트폴리오 추가 */
  async function handleAddPortfolio() {
    if (portfolioStatus !== 'idle') return
    setPortfolioStatus('loading')
    try {
      await addToPortfolio(normalizedTicker)
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
      await addToWatchlist(normalizedTicker)
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
  const qualityToneColor = qualityColor(herdData?.qualityLevel)
  const actionColor = actionTone(herdData?.actionGrade, herdData?.signal)
  const holding    = portfolio.find((item) => item.ticker === normalizedTicker) ?? null
  const decision   = useMemo(() => buildDecision({
    herdData: { ...herdData, ticker: normalizedTicker },
    holding,
    summary: portfolioSummary,
  }), [herdData, holding, portfolioSummary, normalizedTicker])
  const currentReliability = useMemo(
    () => currentSignalReliability(herdData, reliability),
    [herdData, reliability]
  )
  const reliabilityEvidence = useMemo(
    () => reliabilityEvidenceItems(reliability),
    [reliability]
  )
  const fundamentalGuard = useMemo(
    () => evaluateFundamentalGuard(financials, herdData),
    [financials, herdData]
  )
  const signalEvidence = useMemo(
    () => buildSignalEvidence(herdData),
    [herdData]
  )
  const journalSummary = useMemo(
    () => summarizeSignalJournal(signalLogs),
    [signalLogs]
  )
  const historyPoints = useMemo(() => {
    if (herdHistory.length > 0) return herdHistory
    if (!herdData?.scoreDate) return []
    return [{ date: herdData.scoreDate, score: herdScore }]
  }, [herdHistory, herdData, herdScore])
  const herdMomentum = useMemo(
    () => getHerdMomentum(historyPoints, herdScore, herdStage),
    [historyPoints, herdScore, herdStage]
  )

  async function handleJournalAction(actionType, details = {}) {
    try {
      const res = await createSignalJournal({
        ticker: normalizedTicker,
        actionType,
        actionLabel: journalActionLabel(actionType),
        scoreDate: herdData.scoreDate,
        herdScore: Math.round(herdScore),
        herdStage: stageDisp,
        signal: herdData.signal,
        signalLabel: herdData.actionLabel ?? decision.title,
        actionRatio: herdData.actionRatio,
        signalDurationDays: herdData.signalDurationDays,
        stageDurationDays: herdData.stageDurationDays,
        price: details.price,
        quantity: details.quantity,
        amount: details.amount,
        profitPct: details.profitPct,
        memo: details.memo,
      })
      const saved = res.data?.data
      if (saved) {
        setSignalLogs((prev) => [saved, ...prev].slice(0, 5))
      } else {
        await fetchSignalLogs()
      }
    } catch {
      await fetchSignalLogs()
    }
    setJournalAction(null)
  }

  async function handleJournalDelete(id) {
    try {
      await deleteSignalJournal(id)
      setSignalLogs((prev) => prev.filter((log) => log.id !== id))
    } catch {
      await fetchSignalLogs()
    }
  }

  return (
    <div>

      {/* ── 브레드크럼 ── */}
      <div className={styles.breadcrumb}>
        <span className={styles.breadcrumbLink} onClick={() => navigate('/')}>
          포트폴리오
        </span>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{normalizedTicker}</span>
      </div>

      {/* ── 종목 헤더 ── */}
      <div className={styles.stockHeader}>
        <div className={styles.stockHeaderLeft}>
          <StockAvatar
            ticker={normalizedTicker}
            logoUrl={herdData?.logoUrl}
            size="lg"
            tone={herdData ? badgeColors(herdStage) : undefined}
          />
          <div>
            <div className={styles.stockTicker}>{normalizedTicker}</div>
            <div className={styles.stockFullname}>
              {[herdData?.companyName, herdData?.sector].filter(Boolean).join(' · ') || '미국 주식'}
            </div>
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
                  <>
                    <div
                      className={styles.qualityPill}
                      style={{ color: qualityToneColor, borderColor: qualityToneColor }}
                      title={qualityReasonText(herdData)}
                    >
                      {qualityWarningText(herdData, { pointSuffix: true })}
                    </div>
                    <div className={styles.qualityReason}>{qualityReasonText(herdData)}</div>
                  </>
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
                    <div className={styles.decisionBasis}>
                      {formatActionBasis(herdData)}
                    </div>
                    {formatSignalDurationDetail(herdData) && (
                      <div className={styles.decisionBasis}>
                        {formatSignalAgeLabel(herdData)}
                      </div>
                    )}
                    <div className={`${styles.decisionMomentum} ${styles[`decisionMomentum_${herdMomentum.tone}`] || ''}`}>
                      <span>{herdMomentum.label}</span>
                      <strong>{herdMomentum.detail}</strong>
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

            {/* 신호 근거 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>신호 근거</div>
                  <div className={styles.cardMeta}>현재 HERD 판단을 움직인 데이터</div>
                </div>
                <div className={styles.cardMeta}>{herdData.scoreDate} 기준</div>
              </div>
              <div className={styles.cardBodySmall}>
                <div className={styles.evidenceGrid}>
                  {signalEvidence.map((item) => (
                    <div key={`${item.label}-${item.caption}`} className={styles.evidenceItem}>
                      <span>{item.label}</span>
                      <strong style={{ color: evidenceTone(item.type) }}>{item.value}</strong>
                      <em>{item.caption}</em>
                    </div>
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
              </div>
            </div>

            {/* HERD 신호 신뢰도 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>신호 검증</div>
                  <div className={styles.cardMeta}>최근 3년 HERD 히스토리</div>
                </div>
                {reliability && (
                  <div
                    className={styles.reliabilityBadge}
                    style={{
                      color: reliabilityTone(reliability.reliabilityGrade),
                      borderColor: reliabilityTone(reliability.reliabilityGrade),
                    }}
                  >
                    {reliability.reliabilityLabel}
                  </div>
                )}
              </div>
              <div className={styles.cardBodySmall}>
                {reliabilityLoading ? (
                  <div className={styles.chartEmpty}>로딩 중…</div>
                ) : reliability ? (
                  <>
                    {currentReliability && (
                      <div className={styles.currentReliability}>
                        <div>
                          <span>{currentReliability.label}</span>
                          <strong>
                            {currentReliability.scoreValue
                              ? fmtReliabilityScore(currentReliability.value)
                              : fmtReliabilityPlainPct(currentReliability.value)}
                          </strong>
                        </div>
                        <em>
                          {currentReliability.caption}
                          {currentReliability.sample != null ? ` · ${currentReliability.sample}회` : ''}
                        </em>
                      </div>
                    )}
                    <div className={styles.reliabilityGrid}>
                      <div className={styles.reliabilityItem}>
                        <span>모델 적합도</span>
                        <strong>{fmtReliabilityScore(reliability.fitScore)}</strong>
                        <em>{reliability.reliabilityLabel}</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>표본 품질</span>
                        <strong>{sampleQualityLabel(reliability.sampleQuality)}</strong>
                        <em>{reliability.totalSignalSamples ?? 0}회</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>Flee 적중률</span>
                        <strong>{fmtReliabilityPlainPct(reliability.fleeHitRate)}</strong>
                        <em>{signalEdgeLabel(reliability.buySignalEdge)}</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>Rush 적중률</span>
                        <strong>{fmtReliabilityPlainPct(reliability.rushHitRate)}</strong>
                        <em>{signalEdgeLabel(reliability.sellSignalEdge)}</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>MDD 개선</span>
                        <strong>{fmtReliabilityPct(reliability.mddImprovement, '%p')}</strong>
                        <em>낙폭 관리</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>수익률 보존</span>
                        <strong>{fmtReliabilityPlainPct(reliability.returnPreservation)}</strong>
                        <em>Buy & Hold 대비</em>
                      </div>
                      <div className={styles.reliabilityItem}>
                        <span>연 행동 수</span>
                        <strong>{fmtAnnualActions(reliability.annualActions)}</strong>
                        <em>과매매 체크</em>
                      </div>
                    </div>
                    {reliabilityEvidence.length > 0 && (
                      <div className={styles.reliabilityEvidenceGrid}>
                        {reliabilityEvidence.map((item) => (
                          <div
                            key={item.label}
                            className={`${styles.reliabilityEvidenceItem} ${styles[`reliabilityEvidence_${item.tone}`] || ''}`}
                          >
                            <span>{item.label}</span>
                            <strong>{item.value}</strong>
                            <em>{item.caption}</em>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className={styles.reliabilitySummary}>
                      {reliability.reliabilityVerdict ?? reliability.summary}
                    </div>
                  </>
                ) : (
                  <div className={styles.chartEmpty}>신뢰도 데이터를 계산할 수 없습니다.</div>
                )}
              </div>
            </div>

            {/* HERD 히스토리 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>HERD Index History</div>
                  <div className={styles.cardMeta}>1M · 3M · 1Y · 3Y</div>
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

            {/* Fundamental Guard 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>재무 가드</div>
                  <div className={styles.cardMeta}>HERD 신호 보조 필터</div>
                </div>
                {!financialsLoading && (
                  <div
                    className={styles.fundamentalBadge}
                    style={{
                      color: fundamentalTone(fundamentalGuard.level),
                      borderColor: fundamentalTone(fundamentalGuard.level),
                    }}
                  >
                    {fundamentalGuard.label}
                  </div>
                )}
              </div>
              <div className={styles.cardBodySmall}>
                {financialsLoading ? (
                  <div className={styles.chartEmpty}>로딩 중…</div>
                ) : (
                  <>
                    <div className={styles.fundamentalSummary}>
                      {fundamentalGuard.summary}
                    </div>
                    <div className={styles.fundamentalGrid}>
                      <div className={styles.fundamentalItem}>
                        <span>시가총액</span>
                        <strong>{fmtCurrencyCompact(financials?.marketCap)}</strong>
                      </div>
                      <div className={styles.fundamentalItem}>
                        <span>PER</span>
                        <strong>{fmtNumber(financials?.trailingPe)}</strong>
                      </div>
                      <div className={styles.fundamentalItem}>
                        <span>EPS</span>
                        <strong>{fmtNumber(financials?.eps, 2)}</strong>
                      </div>
                      <div className={styles.fundamentalItem}>
                        <span>영업이익률</span>
                        <strong>{fmtFinancePct(financials?.operatingMargin)}</strong>
                      </div>
                      <div className={styles.fundamentalItem}>
                        <span>매출</span>
                        <strong>{fmtCurrencyCompact(financials?.totalRevenue)}</strong>
                      </div>
                    </div>
                    {fundamentalGuard.reasons.length > 0 && (
                      <div className={styles.fundamentalReasons}>
                        {fundamentalGuard.reasons.map((reason) => (
                          <span key={reason}>{reason}</span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* 내 판단 기록 카드 */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <div className={styles.cardTitle}>내 판단 기록</div>
                  <div className={styles.cardMeta}>HERD 신호를 보고 남긴 실사용 로그</div>
                </div>
                <div className={styles.cardMeta}>{formatJournalCount(journalSummary.totalCount)}</div>
              </div>
              <div className={styles.cardBodySmall}>
                <div className={styles.journalSummaryGrid}>
                  <div className={styles.journalSummaryItem}>
                    <span>매수 기록</span>
                    <strong>{formatJournalCount(journalSummary.buyCount)}</strong>
                    <em>{formatJournalAmount(journalSummary.buyAmount) ?? '$0'}</em>
                  </div>
                  <div className={styles.journalSummaryItem}>
                    <span>익절 기록</span>
                    <strong>{formatJournalCount(journalSummary.sellCount)}</strong>
                    <em>{formatJournalAmount(journalSummary.sellAmount) ?? '$0'}</em>
                  </div>
                  <div className={styles.journalSummaryItem}>
                    <span>평균 익절률</span>
                    <strong>{journalSummary.hasProfitData ? formatJournalProfit(journalSummary.avgProfitPct) : '—'}</strong>
                    <em>입력 기록 기준</em>
                  </div>
                </div>
                <div className={styles.journalActions}>
                  <button type="button" className={styles.journalBtn} onClick={() => setJournalAction('BUY')}>
                    매수 기록
                  </button>
                  <button type="button" className={styles.journalBtn} onClick={() => setJournalAction('HOLD')}>
                    보류 기록
                  </button>
                  <button type="button" className={styles.journalBtn} onClick={() => setJournalAction('SELL')}>
                    익절 기록
                  </button>
                </div>
                {signalLogs.length > 0 ? (
                  <div className={styles.journalList}>
                    {signalLogs.slice(0, 3).map((log) => (
                      <div key={log.id} className={styles.journalItem}>
                        <span>{formatJournalTime(log.recordedAt ?? log.createdAt)}</span>
                        <strong>{log.actionLabel}</strong>
                        <em>
                          {[
                            formatJournalPrice(log.price),
                            formatJournalQuantity(log.quantity),
                            formatJournalAmount(log.amount),
                            formatJournalProfit(log.profitPct),
                          ].filter(Boolean).join(' · ') || `HERD ${log.herdScore} · ${log.signalLabel}`}
                        </em>
                        {log.memo && <small>{log.memo}</small>}
                        <button
                          type="button"
                          className={styles.journalDelete}
                          onClick={() => handleJournalDelete(log.id)}
                          aria-label={`${log.actionLabel} 삭제`}
                        >
                          삭제
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={styles.journalEmpty}>
                    아직 기록이 없습니다.
                  </div>
                )}
              </div>
            </div>

          </div>
        </div>
      )}
      {journalAction && (
        <SignalJournalModal
          ticker={normalizedTicker}
          actionType={journalAction}
          herdSnapshot={{
            score: Math.round(herdScore),
            stage: stageDisp,
            signalLabel: herdData?.actionLabel ?? decision.title,
          }}
          onClose={() => setJournalAction(null)}
          onSave={(details) => handleJournalAction(journalAction, details)}
        />
      )}
    </div>
  )
}
