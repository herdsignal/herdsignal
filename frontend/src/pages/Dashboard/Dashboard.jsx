/**
 * Dashboard.jsx — 포트폴리오 대시보드 (/)
 *
 * 섹션 순서:
 *   1) 페이지 헤더 (새로고침·편집·종목 추가 버튼)
 *   2) S&P500 HERD 배너 — 시장 온도 먼저 파악
 *   3) 포트폴리오 평가금액 요약 카드 (통화 토글 포함)
 *   4) 보유 종목 2열 카드 그리드 (편집 모드 지원)
 *   5) 빈 상태 UI
 *
 * 데이터 소스:
 *   - getPortfolio()          → 종목 목록 + avgPrice/quantity (항상 최신 호출)
 *   - getPortfolioSummary()   → DB 기준 포트폴리오 요약 (캐시 우선)
 *   - getPortfolioHerd()      → HERD 점수 (캐시 우선)
 *   - getStockHerd('SPY')     → SPY 배너용 HERD (캐시 우선)
 *
 * 캐시 정책:
 *   최초 진입 → localStorage 캐시 있으면 즉시 표시 (realtime/herd API 호출 없음)
 *             → 캐시 없으면 API 호출 후 캐시 저장
 *   새로고침 버튼 → API 강제 호출 → 결과 캐시 저장
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts'
import {
  getPortfolio,
  getPortfolioSummary,
  getPortfolioHerd,
  getStockHerd,
  getSpyHerdHistory,
  removeFromPortfolio,
} from '../../api/herdApi'
import { fetchExchangeRate, formatKRW } from '../../utils/currency'
import { signalDesc as decisionSignalDesc } from '../../utils/decision'
import HerdDots      from '../../components/HerdDots/HerdDots'
import SpectrumBar   from '../../components/SpectrumBar/SpectrumBar'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import styles        from './Dashboard.module.css'

const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

/* ── localStorage 캐시 키 ──────────────────── */
const CACHE_KEY_REALTIME    = 'hs_portfolio_realtime'
const CACHE_KEY_HERD        = 'hs_portfolio_herd'
const CACHE_KEY_SPY         = 'hs_spy_herd'
const CACHE_KEY_SPY_HISTORY = 'hs_spy_history'
const CACHE_KEY_TIME        = 'hs_cache_time'

/** localStorage에서 JSON 파싱. 실패 시 null 반환 */
function readCache(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** localStorage에 JSON 저장. 실패 시 조용히 무시 */
function writeCache(key, data) {
  try {
    localStorage.setItem(key, JSON.stringify(data))
  } catch { /* 용량 초과 등 무시 */ }
}

/** backend camelCase / Python snake_case 포트폴리오 요약을 화면 모델(snake_case)로 통일 */
function normalizePortfolioSummary(data) {
  if (!data) return null
  return {
    total_value:      data.total_value      ?? data.totalValue      ?? null,
    total_cost:       data.total_cost       ?? data.totalCost       ?? null,
    total_return_pct: data.total_return_pct ?? data.totalReturnPct  ?? null,
    daily_change_pct: data.daily_change_pct ?? data.dailyChangePct  ?? null,
    stocks: (data.stocks ?? []).map((s) => ({
      ticker:           s.ticker,
      avg_price:        s.avg_price        ?? s.avgPrice        ?? null,
      quantity:         s.quantity         ?? null,
      current_price:    s.current_price    ?? s.currentPrice    ?? null,
      market_value:     s.market_value     ?? s.marketValue     ?? null,
      return_pct:       s.return_pct       ?? s.returnPct       ?? null,
      daily_change_pct: s.daily_change_pct ?? s.dailyChangePct  ?? null,
    })),
  }
}

/** 캐시 저장 시각을 ISO string으로 기록하고 Date 객체 반환 */
function saveCacheTime() {
  const now = new Date()
  localStorage.setItem(CACHE_KEY_TIME, now.toISOString())
  return now
}

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
    case 'rush':    return '극단적 과열 · 적극 익절'
    case 'drift':   return '탐욕 · 일부 익절 고려'
    case 'scatter': return '공포 · 분할 매수'
    case 'flee':    return '극단적 공포 · 적극 매수'
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

/** 업데이트 완료 시간 포맷: "오후 1:35" */
function fmtTime(date) {
  if (!date) return ''
  return date.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })
}

/**
 * SPY scoreDate 스마트 포맷 (KST 기준).
 * - 오늘: "오늘 HH:MM"  (fetchTime이 있으면 그 시각, 없으면 현재 시각)
 * - 어제: "어제"
 * - 그 이전: "MM월 DD일"
 */
function fmtScoreDate(dateStr, fetchTime) {
  if (!dateStr) return '—'

  const nowKST = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Seoul' }))
  const pad    = (n) => String(n).padStart(2, '0')
  const todayStr = `${nowKST.getFullYear()}-${pad(nowKST.getMonth() + 1)}-${pad(nowKST.getDate())}`
  const ystKST   = new Date(nowKST)
  ystKST.setDate(ystKST.getDate() - 1)
  const ystStr = `${ystKST.getFullYear()}-${pad(ystKST.getMonth() + 1)}-${pad(ystKST.getDate())}`

  if (dateStr === todayStr) {
    const t = fetchTime ?? new Date()
    return `오늘 ${t.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })}`
  }
  if (dateStr === ystStr) return '어제'

  const d = new Date(dateStr)
  return isNaN(d) ? dateStr : d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

/** HERD 점수 → 단계 색상 (히스토리 통계용) */
function scoreToColor(score) {
  if (score == null) return 'var(--text-1)'
  if (score < 20) return 'var(--flee)'
  if (score < 40) return 'var(--scatter)'
  if (score < 60) return 'var(--calm)'
  if (score < 80) return 'var(--drift)'
  return 'var(--rush)'
}

/** HERD 점수 → 단계명 (히스토리 통계용) */
function scoreToStage(score) {
  if (score == null) return null
  if (score < 20) return 'Herd Flee'
  if (score < 40) return 'Herd Scatter'
  if (score < 60) return 'Herd Calm'
  if (score < 80) return 'Herd Drift'
  return 'Herd Rush'
}

/** points 배열에서 targetDate에 가장 가까운 포인트 반환 */
function findScoreAt(points, targetDate) {
  if (!points?.length) return null
  const target = targetDate.getTime()
  let closest = null
  let minDiff = Infinity
  for (const p of points) {
    const pointDate = new Date(`${p.date}T00:00:00`)
    const pointTime = pointDate.getTime()
    if (Number.isNaN(pointTime)) continue
    const diff = Math.abs(pointTime - target)
    if (diff < minDiff) { minDiff = diff; closest = p }
  }
  return closest
}

/** "2023-07-01" → "2023.07" (X축 눈금 포맷) */
function fmtHistAxisDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}`
}

/** Timeline 차트 커스텀 툴팁 */
function HistTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const score = payload[0]?.value
  return (
    <div className={styles.histTooltip}>
      <div className={styles.histTooltipDate}>
        {label
          ? new Date(label + 'T00:00:00').toLocaleDateString('ko-KR', {
              year: 'numeric', month: 'long', day: 'numeric',
            })
          : ''}
      </div>
      <div style={{ color: scoreToColor(score), fontFamily: 'Space Grotesk', fontWeight: 600 }}>
        HERD {score != null ? Math.round(score) : '—'}
      </div>
    </div>
  )
}

function BannerStat({ label, point }) {
  const stage = scoreToStage(point?.score)

  return (
    <div className={styles.bannerStatItem}>
      <div className={styles.bannerStatLabel}>{label}</div>
      {point && stage ? (
        <>
          <div className={styles.bannerStatMain}>
            <span className={styles.bannerStatValue} style={{ color: scoreToColor(point.score) }}>
              {Math.round(point.score)}
            </span>
            <span className={styles.bannerStatStage}>{stage}</span>
          </div>
          <div className={styles.bannerStatDesc}>{stageDesc(stage)}</div>
        </>
      ) : (
        <div className={styles.bannerStatValue}>—</div>
      )}
    </div>
  )
}

/* ── 컴포넌트 ─────────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate()

  const [portfolio,      setPortfolio]      = useState([])
  const [summary,        setSummary]        = useState(null)
  const [herdMap,        setHerdMap]        = useState({})
  const [spyData,        setSpyData]        = useState(null)
  const [spyHistory,     setSpyHistory]     = useState([])
  const [spyTab,         setSpyTab]         = useState('overview')
  /*
   * SPY 데이터 ref 캐시 — React 18 Strict Mode가 effect를 cleanup → 재실행할 때
   * state는 초기화되지만 ref는 유지된다. 두 번째 실행에서 ref 값을 즉시 state에 반영.
   */
  const spyDataCache    = useRef(null)
  const spyHistoryCache = useRef(null)
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  const [modalTicker,    setModalTicker]    = useState(null)
  const [deletingTicker, setDeletingTicker] = useState(null)
  const [exchangeRate,   setExchangeRate]   = useState(null)
  const [refreshing,     setRefreshing]     = useState(false)
  /*
   * 마지막 캐시 저장 시각 — localStorage 'hs_cache_time'에서 초기화.
   * 캐시 없으면 null (헤더에 업데이트 시각 미표시).
   */
  const [lastUpdated,    setLastUpdated]    = useState(() => {
    const t = localStorage.getItem(CACHE_KEY_TIME)
    return t ? new Date(t) : null
  })
  const [currencyMode,   setCurrencyMode]   = useState(
    () => localStorage.getItem('herdsignal_currency') || 'KRW'
  )
  const [editMode,       setEditMode]       = useState(false)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* ── 포트폴리오 데이터 로딩 (캐시 우선) ── */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      /*
       * (1) 종목 목록 — 항상 최신 조회.
       *     avgPrice/quantity는 사용자가 언제든 변경할 수 있으므로 캐시 사용 안 함.
       */
      const portfolioRes = await getPortfolio().catch(() => null)
      if (portfolioRes) {
        const raw = portfolioRes.data?.data
        setPortfolio(Array.isArray(raw) ? raw : [])
      } else {
        setPortfolio([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
        return
      }

      /*
       * (2) 실시간 가격 / HERD 점수 — localStorage 캐시 우선.
       *     캐시 있으면 API 호출 없이 즉시 세팅 (새로고침 버튼으로만 갱신 가능).
       *     캐시 없으면 API 호출 후 저장.
       */
      const cachedSummary = readCache(CACHE_KEY_REALTIME)
      const cachedHerd    = readCache(CACHE_KEY_HERD)

      if (cachedSummary) {
        /* 캐시 히트 — 즉시 세팅 */
        setSummary(cachedSummary)
        const map = {}
        if (cachedHerd?.stocks) {
          cachedHerd.stocks.forEach((h) => { map[h.ticker] = h })
        }
        setHerdMap(map)
        /* lastUpdated는 state 초기화 시 hs_cache_time에서 이미 읽음 */
      } else {
        /* 캐시 미스 — API 호출 (첫 방문 케이스) */
        const [summaryRes, herdRes] = await Promise.allSettled([
          getPortfolioSummary(),
          getPortfolioHerd(),
        ])
        if (summaryRes.status === 'fulfilled') {
          const data = normalizePortfolioSummary(summaryRes.value.data?.data ?? null)
          setSummary(data)
          writeCache(CACHE_KEY_REALTIME, data)
        }
        const map = {}
        if (herdRes.status === 'fulfilled') {
          const herdData = herdRes.value?.data?.data ?? null
          const herdStocks = herdData?.stocks ?? []
          herdStocks.forEach((h) => { map[h.ticker] = h })
          writeCache(CACHE_KEY_HERD, herdData)
        }
        setHerdMap(map)
        setLastUpdated(saveCacheTime())
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  /*
   * SPY 배너 — 포트폴리오 로딩과 완전히 분리.
   * ref 캐시(Strict Mode 대응) → localStorage 캐시 → API 호출 순서로 처리.
   * HERD 점수 + 3년 히스토리 동시 로딩.
   */
  useEffect(() => {
    const herdCached    = spyDataCache.current    ?? readCache(CACHE_KEY_SPY)
    const historyCached = spyHistoryCache.current ?? readCache(CACHE_KEY_SPY_HISTORY)

    if (herdCached) {
      spyDataCache.current = herdCached
      setSpyData(herdCached)
    }
    if (historyCached) {
      spyHistoryCache.current = historyCached
      setSpyHistory(historyCached)
    }

    if (herdCached && historyCached) return

    if (!herdCached) {
      getStockHerd('SPY')
        .then((res) => {
          const data = res.data?.data ?? null
          spyDataCache.current = data
          setSpyData(data)
          writeCache(CACHE_KEY_SPY, data)
        })
        .catch(() => { /* SPY HERD 실패 시 배너 기본값(Calm/50) 유지 */ })
    }

    if (!historyCached) {
      getSpyHerdHistory('3y')
        .then((res) => {
          const points = res.data?.data?.points ?? []
          spyHistoryCache.current = points
          setSpyHistory(points)
          writeCache(CACHE_KEY_SPY_HISTORY, points)
        })
        .catch(() => { /* 히스토리 실패 시 Timeline 탭 빈 상태 유지 */ })
    }
  }, [])

  /* USD/KRW 환율 — 마운트 시 1회 조회 */
  useEffect(() => {
    fetchExchangeRate().then(setExchangeRate)
  }, [])

  /* ticker → 현재가 데이터 맵 (Python snake_case) */
  const priceMap = useMemo(() => {
    const map = {}
    summary?.stocks?.forEach((s) => { map[s.ticker] = s })
    return map
  }, [summary])

  /* 통화 모드 전환 — localStorage에 저장 */
  const handleCurrencyToggle = useCallback((mode) => {
    setCurrencyMode(mode)
    localStorage.setItem('herdsignal_currency', mode)
  }, [])

  /**
   * USD 금액 → 통화 모드에 맞게 표시.
   * 원화: "22,515,837원" / 달러: "$14,518.01"
   */
  const displayAmount = useCallback((usdValue) => {
    if (usdValue == null) return '—'
    if (currencyMode === 'KRW' && exchangeRate != null) {
      return formatKRW(usdValue, exchangeRate)
    }
    return fmtUSD(usdValue)
  }, [currencyMode, exchangeRate])

  /**
   * USD 손익 → 통화 모드에 맞게 부호 포함 표시.
   * 원화: "+3,139,172원" / 달러: "+$1,234.56"
   */
  const displayPnl = useCallback((usdPnl) => {
    if (usdPnl == null) return '—'
    const n    = Number(usdPnl)
    const sign = n >= 0 ? '+' : ''
    if (currencyMode === 'KRW' && exchangeRate != null) {
      const krw = Math.round(n * exchangeRate)
      return `${sign}${krw.toLocaleString('ko-KR')}원`
    }
    const absStr = Math.abs(n).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    return `${n < 0 ? '-' : '+'}$${absStr}`
  }, [currencyMode, exchangeRate])

  /*
   * 수동 새로고침 — DB에 저장된 최신 데이터만 빠르게 재조회 후 캐시 갱신.
   * getPortfolio() 제외 (종목 목록은 추가/삭제 시에만 변경됨).
   */
  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const [summaryRes, herdRes, spyRes, spyHistoryRes] = await Promise.allSettled([
        getPortfolioSummary(),
        getPortfolioHerd(),
        getStockHerd('SPY'),
        getSpyHerdHistory('3y'),
      ])

      if (summaryRes.status === 'fulfilled') {
        const data = normalizePortfolioSummary(summaryRes.value.data?.data ?? null)
        setSummary(data)
        writeCache(CACHE_KEY_REALTIME, data)
      }

      if (herdRes.status === 'fulfilled') {
        const map = {}
        const herdData = herdRes.value?.data?.data ?? null
        const herdStocks = herdData?.stocks ?? []
        herdStocks.forEach((h) => { map[h.ticker] = h })
        writeCache(CACHE_KEY_HERD, herdData)
        setHerdMap(map)
      }

      if (spyRes.status === 'fulfilled') {
        const data = spyRes.value.data?.data ?? null
        spyDataCache.current = data
        setSpyData(data)
        writeCache(CACHE_KEY_SPY, data)
      }

      if (spyHistoryRes.status === 'fulfilled') {
        const points = spyHistoryRes.value.data?.data?.points ?? []
        spyHistoryCache.current = points
        setSpyHistory(points)
        writeCache(CACHE_KEY_SPY_HISTORY, points)
      }

      /* 캐시 저장 시각 갱신 — 헤더 "업데이트 · 오후 X:XX" 기준 */
      setLastUpdated(saveCacheTime())
    } finally {
      setRefreshing(false)
    }
  }, [])

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

  /* 히스토리 기준 통계 포인트 (Overview 탭) */
  const ystPoint = useMemo(() => {
    const t = new Date(); t.setDate(t.getDate() - 1)
    return findScoreAt(spyHistory, t)
  }, [spyHistory])
  const m1Point = useMemo(() => {
    const t = new Date(); t.setDate(t.getDate() - 30)
    return findScoreAt(spyHistory, t)
  }, [spyHistory])
  const y1Point = useMemo(() => {
    const t = new Date(); t.setDate(t.getDate() - 365)
    return findScoreAt(spyHistory, t)
  }, [spyHistory])

  /*
   * 모달 저장 완료 → 로컬 상태 즉시 업데이트 + localStorage 캐시 갱신.
   * summary는 항상 USD 단위로 저장. displayAmount/displayPnl이 통화 변환 담당.
   */
  const handleModalSaved = useCallback((newAvgPrice, newQty) => {
    const ticker = modalTicker

    setPortfolio(prev => prev.map(p =>
      p.ticker === ticker ? { ...p, avgPrice: newAvgPrice, quantity: newQty } : p
    ))

    const currentPrice = priceMap[ticker]?.current_price
    if (currentPrice != null) {
      const newMarketValue = currentPrice * newQty
      const newReturnPct   = (currentPrice - newAvgPrice) / newAvgPrice * 100

      setSummary(prev => {
        if (!prev) return prev

        const updatedStocks = (prev.stocks ?? []).map(s =>
          s.ticker === ticker
            ? { ...s, market_value: newMarketValue, return_pct: newReturnPct }
            : s
        )
        const oldMarketValue = priceMap[ticker]?.market_value ?? 0
        const newTotalValue  = (prev.total_value ?? 0) - oldMarketValue + newMarketValue
        const oldStock       = portfolio.find(p => p.ticker === ticker)
        const oldCost        = (oldStock?.avgPrice ?? 0) * (oldStock?.quantity ?? 0)
        const newTotalCost   = (prev.total_cost ?? 0) - oldCost + newAvgPrice * newQty
        const newTotalReturnPct = newTotalCost > 0
          ? (newTotalValue - newTotalCost) / newTotalCost * 100
          : 0

        const next = {
          ...prev,
          stocks:           updatedStocks,
          total_value:      newTotalValue,
          total_cost:       newTotalCost,
          total_return_pct: newTotalReturnPct,
        }
        /* 캐시도 함께 갱신 — 다음 방문 시 수정된 수익률 표시 */
        writeCache(CACHE_KEY_REALTIME, next)
        return next
      })
    } else {
      fetchData()
    }

    setModalTicker(null)
  }, [modalTicker, priceMap, portfolio, fetchData])

  const modalStock = portfolio.find((p) => p.ticker === modalTicker)

  return (
    <div>

      {/* ── 페이지 헤더 ── */}
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>내 포트폴리오</h1>
        </div>
        <div className={styles.headerActions}>
          {/* 마지막 캐시 저장 시각 — localStorage 'hs_cache_time' 기준 */}
          {lastUpdated && (
            <span className={styles.updateTime}>
              업데이트 · {fmtTime(lastUpdated)}
            </span>
          )}
          <button
            className={styles.btnRefresh}
            onClick={handleRefresh}
            disabled={refreshing || loading}
          >
            {refreshing ? '새로고침 중…' : '↻ 새로고침'}
          </button>
          <button
            className={`${styles.btnEdit} ${editMode ? styles.btnEditActive : ''}`}
            onClick={() => setEditMode(m => !m)}
          >
            {editMode ? '완료' : '편집'}
          </button>
          <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
            종목 추가
          </button>
        </div>
      </div>

      {/* ── S&P500 HERD 배너 ── */}
      <div className={styles.marketBanner}>
        {/* 좌: 점수·단계 블록 */}
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

        {/* 우: 탭 + 컨텐츠 */}
        <div className={styles.bannerRight}>
          {/* 탭 버튼 */}
          <div className={styles.bannerTabs}>
            <button
              className={`${styles.bannerTab} ${spyTab === 'overview' ? styles.bannerTabActive : ''}`}
              onClick={() => setSpyTab('overview')}
            >Overview</button>
            <button
              className={`${styles.bannerTab} ${spyTab === 'timeline' ? styles.bannerTabActive : ''}`}
              onClick={() => setSpyTab('timeline')}
            >Timeline</button>
          </div>

          {/* Overview 탭 */}
          {spyTab === 'overview' && (
            <div className={styles.bannerOverview}>
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
              <div className={styles.bannerHistStats}>
                <BannerStat label="어제" point={ystPoint} />
                <BannerStat label="1달 전" point={m1Point} />
                <BannerStat label="1년 전" point={y1Point} />
                <div className={styles.bannerStatItem}>
                  <div className={styles.bannerStatLabel}>업데이트</div>
                  <div className={styles.bannerStatUpdate}>
                    {spyData ? fmtScoreDate(spyData.scoreDate, lastUpdated) : '—'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Timeline 탭 */}
          {spyTab === 'timeline' && (
            <div className={styles.bannerTimeline}>
              {spyHistory.length === 0 ? (
                <div className={styles.bannerTimelineEmpty}>데이터 없음</div>
              ) : (
                <ResponsiveContainer width="100%" height={190}>
                  <LineChart data={spyHistory} margin={{ top: 8, right: 20, left: 0, bottom: 4 }}>
                    <ReferenceArea y1={0}  y2={20}  fill="#3B82F6" fillOpacity={0.08} />
                    <ReferenceArea y1={20} y2={40}  fill="#93C5FD" fillOpacity={0.08} />
                    <ReferenceArea y1={40} y2={60}  fill="#9CA3AF" fillOpacity={0.05} />
                    <ReferenceArea y1={60} y2={80}  fill="#FB923C" fillOpacity={0.08} />
                    <ReferenceArea y1={80} y2={100} fill="#EF4444" fillOpacity={0.08} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={fmtHistAxisDate}
                      interval={Math.max(0, Math.floor(spyHistory.length / 6) - 1)}
                      tick={{ fontSize: 10, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                      axisLine={false}
                      tickLine={false}
                      tickMargin={6}
                    />
                    <YAxis
                      domain={[0, 100]}
                      ticks={[0, 20, 40, 60, 80, 100]}
                      tick={{ fontSize: 10, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                      axisLine={false}
                      tickLine={false}
                      width={28}
                    />
                    <Tooltip content={<HistTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="score"
                      stroke="rgba(255,255,255,0.65)"
                      strokeWidth={1.5}
                      dot={false}
                      activeDot={{ r: 3, fill: 'rgba(255,255,255,0.9)', strokeWidth: 0 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
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

      {/* ── 포트폴리오 평가금액 요약 카드 ── */}
      {summary && (
        <>
          <div className={styles.summarySectionHeader}>
            <div className={styles.sectionTitle}>포트폴리오 평가</div>
            <div className={styles.currencyToggle}>
              <button
                className={`${styles.currencyBtn} ${currencyMode === 'KRW' ? styles.currencyBtnActive : ''}`}
                onClick={() => handleCurrencyToggle('KRW')}
              >
                ₩ 원화
              </button>
              <button
                className={`${styles.currencyBtn} ${currencyMode === 'USD' ? styles.currencyBtnActive : ''}`}
                onClick={() => handleCurrencyToggle('USD')}
              >
                $ 달러
              </button>
            </div>
          </div>

          <div className={styles.summarySection}>
            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>총 평가금액</div>
              <div className={styles.summaryValue}>
                {displayAmount(summary.total_value)}
              </div>
              <div
                className={styles.summaryPnl}
                style={{ color: pctColor(summary.total_return_pct) }}
              >
                {displayPnl(summary.total_value - summary.total_cost)} ({fmtPct(summary.total_return_pct)})
              </div>
              <div className={styles.summarySub}>
                매입 {displayAmount(summary.total_cost)}
              </div>
            </div>

            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>총 수익률</div>
              <div
                className={styles.summaryValue}
                style={{ color: pctColor(summary.total_return_pct) }}
              >
                {fmtPct(summary.total_return_pct)}
              </div>
              <div className={styles.summarySub}>
                {summary.total_return_pct >= 0 ? '평가이익' : '평가손실'}
              </div>
            </div>

            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>오늘 등락</div>
              <div
                className={styles.summaryValue}
                style={{ color: pctColor(summary.daily_change_pct) }}
              >
                {fmtPct(summary.daily_change_pct)}
              </div>
              <div className={styles.summarySub}>전일 대비</div>
            </div>
          </div>

          {exchangeRate != null && (
            <div className={styles.exchangeRateRow}>
              <span className={styles.exchangeRateText}>
                {`USD/KRW ${Number(exchangeRate).toLocaleString('ko-KR', {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })} · 15분 지연`}
              </span>
            </div>
          )}
        </>
      )}

      {/* ── 종목 카드 그리드 ── */}
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
              const stageName = stage.startsWith('Herd ') ? stage.slice(5) : stage

              const price       = priceMap[item.ticker]
              const hasAvgPrice = item.avgPrice != null && item.quantity != null
              const isDeleting  = deletingTicker === item.ticker

              /* 종목 손익 = 평가금액 - 매입금액(평단가 × 수량) */
              const pnlUsd = (hasAvgPrice && price)
                ? price.market_value - item.avgPrice * item.quantity
                : null

              return (
                <div
                  key={item.ticker}
                  className={`${styles.stockCard} ${editMode ? styles.stockCardEdit : ''}`}
                  onClick={editMode ? undefined : () => navigate(`/stock/${item.ticker}`)}
                  style={{ opacity: isDeleting ? 0.4 : 1 }}
                >
                  <div className={styles.cardStripe} style={{ background: color }} />

                  {editMode && (
                    <button
                      className={styles.cardDeleteBtn}
                      style={{ opacity: 1 }}
                      onClick={e => handleDelete(e, item.ticker)}
                      disabled={!!deletingTicker}
                      title={`${item.ticker} 포트폴리오에서 삭제`}
                    >
                      {isDeleting ? '…' : '✕'}
                    </button>
                  )}

                  {/* ─ 상단: 종목명(좌) / HERD점수·단계명·시그널(우) ─ */}
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

                    {/* 우측: HERD 점수 → 단계명 → 시그널 배지 (의미상 한 묶음) */}
                    <div className={styles.cardHerd} style={{ paddingRight: editMode ? '20px' : '4px' }}>
                      {herd ? (
                        <>
                          <div className={styles.cardHerdNum} style={{ color }}>
                            {Math.round(herd.herdScore)}
                          </div>
                          <div className={styles.cardHerdStage}>{stageName}</div>
                          {/* 시그널 배지 — HERD 점수와 의미상 연결되어 같은 블록에 배치 */}
                          <div className={styles.cardSignalGroup}>
                            <span
                              className={styles.cardSignalBadge}
                              style={{ background: signal.bg, color: signal.color }}
                            >
                              {herd.signal}
                            </span>
                            <span className={styles.cardSignalDesc}>
                              {decisionSignalDesc(herd.signal)}
                            </span>
                          </div>
                        </>
                      ) : (
                        <span className={styles.cardDash}>—</span>
                      )}
                    </div>
                  </div>

                  {/* ─ 중간: 평가금액 + 손익 (또는 평단가 안내) ─ */}
                  <div className={styles.cardMiddle}>
                    {hasAvgPrice ? (
                      <div>
                        <div className={styles.cardValueLabel}>평가금액</div>
                        <div className={styles.cardValueMain}>
                          {price ? displayAmount(price.market_value) : '—'}
                        </div>
                        {pnlUsd != null && (
                          <div
                            className={styles.cardPnlRow}
                            style={{ color: pctColor(price.return_pct) }}
                          >
                            {displayPnl(pnlUsd)} ({fmtPct(price.return_pct)})
                          </div>
                        )}
                        {editMode && (
                          <div style={{ marginTop: '8px' }}>
                            <button
                              className={styles.cardInputBtn}
                              onClick={e => {
                                e.stopPropagation()
                                setModalTicker(item.ticker)
                              }}
                            >
                              수정
                            </button>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className={styles.cardNoPrice}>
                        <span className={styles.cardNoPriceText}>
                          평단가를 입력하면 수익률을 확인할 수 있어요
                        </span>
                        {editMode && (
                          <button
                            className={styles.cardInputBtn}
                            onClick={e => {
                              e.stopPropagation()
                              setModalTicker(item.ticker)
                            }}
                          >
                            입력
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {/* ─ 하단: 현재가 · 오늘 등락 (평단가 여부 무관) ─ */}
                  <div className={styles.cardBottom}>
                    {price ? (
                      <div className={styles.cardPriceInfo}>
                        <span className={styles.cardCurrentPrice}>
                          현재가 {displayAmount(price.current_price)}
                        </span>
                        <span
                          className={styles.cardDailyChange}
                          style={{ color: pctColor(price.daily_change_pct) }}
                        >
                          오늘 {fmtPct(price.daily_change_pct)}
                        </span>
                      </div>
                    ) : (
                      <span className={styles.cardDash}>현재가 —</span>
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

      {/* ── 평단가 입력/수정 모달 ── */}
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
