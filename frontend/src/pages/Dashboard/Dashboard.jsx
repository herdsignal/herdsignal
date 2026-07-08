/**
 * Dashboard.jsx — 포트폴리오 대시보드 (/)
 *
 * 섹션 순서:
 *   1) 페이지 헤더 (새로고침·편집·종목 추가 버튼)
 *   2) Signal Command Center — 시장 HERD 배너 + Action Queue + 포트폴리오 요약
 *   3) 자산 히스토리/판단 기록 보조 패널
 *   4) 보유 종목 테이블 리스트 (편집 모드 지원)
 *   5) 빈 상태 UI
 *
 * 데이터 소스:
 *   - getPortfolio()          → 종목 목록 + avgPrice/quantity (항상 최신 호출)
 *   - getPortfolioSummary()   → DB 기준 포트폴리오 요약 (캐시 우선)
 *   - getPortfolioRealtime()  → 새로고침 시 yfinance 현재가 기반 평가
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
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import {
  getPortfolio,
  getPortfolioSummary,
  getPortfolioRealtime,
  getPortfolioHerd,
  getStockHerd,
  getSpyHerdHistory,
  getPortfolioHistory,
  getCashBalance,
  updateCashBalance,
  getSignalJournal,
  removeFromPortfolio,
} from '../../api/herdApi'
import { fetchExchangeRate, formatKRW } from '../../utils/currency'
import { signalDesc as decisionSignalDesc } from '../../utils/decision'
import { scoreColor, stageLabelFromScore } from '../../utils/herdStage'
import { formatSignalDuration } from '../../utils/signalDuration'
import {
  portfolioRows,
  readTargetWeights,
  rebalanceIdeas,
  writeTargetWeights,
} from '../../utils/portfolioTools'
import {
  formatJournalAmount,
  formatJournalCount,
  formatJournalProfit,
  summarizeSignalJournal,
} from '../../utils/signalJournal'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import HerdDots      from '../../components/HerdDots/HerdDots'
import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import SpectrumBar   from '../../components/SpectrumBar/SpectrumBar'
import StockAvatar   from '../../components/StockAvatar/StockAvatar'
import styles        from './Dashboard.module.css'

const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

/* ── localStorage 캐시 키 ──────────────────── */
const CACHE_KEY_REALTIME    = 'hs_portfolio_realtime'
const CACHE_KEY_HERD        = 'hs_portfolio_herd'
const CACHE_KEY_SPY         = 'hs_spy_herd'
const CACHE_KEY_SPY_HISTORY = 'hs_spy_history'
const CACHE_KEY_SPY_HISTORY_VERSION = 'v2'
const CACHE_KEY_TIME        = 'hs_cache_time'
const CACHE_KEY_VERSION     = 'hs_dashboard_cache_version'
const CACHE_KEY_PORTFOLIO_SORT = 'hs_dashboard_sort'
const DASHBOARD_CACHE_VERSION = 'v3-logo'

const HISTORY_PERIODS = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '1y', label: '1Y' },
  { value: '3y', label: '3Y' },
]

const ASSET_HISTORY_PERIODS = [
  { value: 'month', label: '1개월' },
  { value: 'year', label: '1년' },
  { value: 'all', label: '전체' },
]

const PORTFOLIO_SORT_OPTIONS = [
  { value: 'action', label: '행동순' },
  { value: 'herdLow', label: 'HERD 낮은순' },
  { value: 'herdHigh', label: 'HERD 높은순' },
  { value: 'weight', label: '비중순' },
]

const REFRESH_SCOPE_TITLE = 'yfinance 현재가, HERD DB 조회, SPY 최신 점수만 갱신합니다. 히스토리와 신뢰도는 각 화면에서 별도 조회됩니다.'

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

function formatInputDate(value) {
  const date = value ? new Date(value) : new Date()
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function spyHistoryCacheKey(period) {
  return `${CACHE_KEY_SPY_HISTORY}_${period}_${CACHE_KEY_SPY_HISTORY_VERSION}`
}

function ensureDashboardCacheVersion() {
  try {
    if (localStorage.getItem(CACHE_KEY_VERSION) === DASHBOARD_CACHE_VERSION) {
      return false
    }

    [
      CACHE_KEY_REALTIME,
      CACHE_KEY_HERD,
      CACHE_KEY_SPY,
      CACHE_KEY_TIME,
      ...HISTORY_PERIODS.map((period) => spyHistoryCacheKey(period.value)),
    ].forEach((key) => localStorage.removeItem(key))

    localStorage.setItem(CACHE_KEY_VERSION, DASHBOARD_CACHE_VERSION)
    return true
  } catch {
    return false
  }
}

function minSpyHistoryPoints(period) {
  switch (period) {
    case '1m': return 4
    case '3m': return 8
    case '1y': return 20
    case '3y': return 50
    default: return 4
  }
}

function isUsableSpyHistoryCache(period, points) {
  return Array.isArray(points) && points.length >= minSpyHistoryPoints(period)
}

/** backend camelCase / Python snake_case 포트폴리오 요약을 화면 모델(snake_case)로 통일 */
function normalizePortfolioSummary(data) {
  if (!data) return null
  const investedValue = data.invested_value ?? data.investedValue ?? data.total_value ?? data.totalValue ?? null
  const cashBalance = data.cash_balance ?? data.cashBalance ?? 0
  const totalAssetValue = data.total_asset_value ?? data.totalAssetValue ??
    (investedValue == null ? null : Number(investedValue) + Number(cashBalance ?? 0))
  return {
    total_value:      totalAssetValue,
    invested_value:   investedValue,
    cash_balance:     cashBalance,
    total_asset_value: totalAssetValue,
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
    case 'rush':    return '군중 밀집 · 적극 익절'
    case 'drift':   return '쏠림 진행 · 일부 익절 고려'
    case 'scatter': return '군중 흩어짐 · 분할 매수'
    case 'flee':    return '군중 이탈 · 적극 매수'
    default:        return '군중 균형 · 보유 유지'
  }
}

/** signal → 배지 배경·텍스트 색 */
function signalStyle(signal) {
  switch (signal) {
    case 'SELL':   return { bg: 'rgba(239,68,68,0.1)',    color: '#EF4444' }
    case 'REDUCE': return { bg: 'rgba(249,115,22,0.1)',   color: '#F97316' }
    case 'HOLD':   return { bg: 'rgba(163,170,184,0.14)', color: 'var(--calm)' }
    case 'ADD':    return { bg: 'rgba(96,165,250,0.12)',  color: '#60A5FA' }
    case 'BUY':    return { bg: 'rgba(59,130,246,0.12)',  color: '#3B82F6' }
    default:       return { bg: 'rgba(163,170,184,0.14)', color: 'var(--calm)' }
  }
}

/** stage → 티커 배지 배경·텍스트 색 */
function badgeStyle(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return { bg: 'rgba(239,68,68,0.12)',   color: 'var(--rush)' }
    case 'drift':   return { bg: 'rgba(249,115,22,0.12)',  color: 'var(--drift)' }
    case 'scatter': return { bg: 'rgba(96,165,250,0.12)',  color: 'var(--scatter)' }
    case 'flee':    return { bg: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:        return { bg: 'rgba(163,170,184,0.13)', color: 'var(--calm)' }
  }
}

function qualityColor(level) {
  switch (level) {
    case 'HIGH': return 'var(--flee)'
    case 'GOOD': return 'var(--calm)'
    case 'LIMITED': return 'var(--drift)'
    case 'LOW': return 'var(--rush)'
    default: return 'var(--text-3)'
  }
}

function shouldShowQuality(herd) {
  if (!herd?.qualityLabel) return false
  if (herd.qualityLevel === 'LIMITED' || herd.qualityLevel === 'LOW') return true
  return Number(herd.qualityScore ?? 100) < 70
}

function qualityWarningText(herd) {
  const label = herd?.qualityLevel === 'LOW' ? '데이터 부족' : '데이터 제한'
  return `${label}${herd?.qualityScore != null ? ` · ${herd.qualityScore}` : ''}`
}

function formatActionScore(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `강도 ${Math.round(n)}`
}

function formatActionText(herd) {
  const action = herd?.actionLabel ?? decisionSignalDesc(herd?.signal)
  const strength = formatActionScore(herd?.actionScore)
  return [strength, action].filter(Boolean).join(' · ')
}

function formatActionBasis(herd) {
  const ratio = Number(herd?.actionRatio ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return '현재 비중 유지'

  const pct = Math.round(ratio * 100)
  if (herd?.signal === 'BUY' || herd?.signal === 'ADD') {
    return `목표 투자금 기준 ${pct}% 분할 투입`
  }
  if (herd?.signal === 'SELL' || herd?.signal === 'REDUCE') {
    return `보유 평가금액 기준 ${pct}% 축소`
  }
  return '현재 비중 유지'
}

function formatActionCode(herd) {
  if (!herd?.signal) return 'HOLD'
  const ratio = Number(herd.actionRatio ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return herd.signal
  return `${herd.signal} ${Math.round(ratio * 100)}%`
}

function positionGap(row) {
  if (!row) return null
  const gap = Number(row.targetWeight ?? 0) - Number(row.currentWeight ?? 0)
  return Number.isFinite(gap) ? gap : null
}

function buildPositionAction(herd, row) {
  const gap = positionGap(row)
  const signal = herd?.signal ?? 'HOLD'
  const isBuy = signal === 'BUY' || signal === 'ADD'
  const isSell = signal === 'SELL' || signal === 'REDUCE'
  const base = {
    code: formatActionCode(herd),
    text: formatActionText(herd),
    basis: formatActionBasis(herd),
    muted: false,
  }

  if (gap == null) return base

  const absGap = Math.abs(gap).toFixed(1)
  if (isBuy && gap < -2) {
    return {
      code: 'WAIT',
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 추가매수 보류`,
      basis: `목표보다 ${absGap}%p 초과 · HERD는 매수권`,
      muted: true,
    }
  }

  if (isBuy && gap > 2) {
    return {
      ...base,
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 목표비중 채우기`,
      basis: `목표까지 ${gap.toFixed(1)}%p 부족 · 분할 투입 우선`,
    }
  }

  if (isSell && gap < -2) {
    return {
      ...base,
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 비중 축소 우선`,
      basis: `목표보다 ${absGap}%p 초과 · 익절 신호와 일치`,
    }
  }

  if (isSell && gap > 2) {
    return {
      ...base,
      text: `${formatActionScore(herd?.actionScore) ?? '강도 확인'} · 익절은 작게`,
      basis: `목표까지 ${gap.toFixed(1)}%p 부족 · 과도한 축소 주의`,
    }
  }

  if (signal === 'HOLD' && Math.abs(gap) > 5) {
    return {
      ...base,
      text: gap > 0 ? '강도 보통 · 비중 부족' : '강도 보통 · 비중 초과',
      basis: gap > 0
        ? `목표까지 ${gap.toFixed(1)}%p 부족 · HERD는 보유`
        : `목표보다 ${absGap}%p 초과 · HERD는 보유`,
    }
  }

  return base
}

function actionPriority(signal) {
  switch (signal) {
    case 'SELL':   return 0
    case 'REDUCE': return 1
    case 'BUY':    return 2
    case 'ADD':    return 3
    case 'HOLD':   return 4
    default:       return 5
  }
}

function queuePriority(actionCode) {
  if (actionCode?.startsWith('SELL')) return 0
  if (actionCode?.startsWith('REDUCE')) return 1
  if (actionCode?.startsWith('BUY')) return 2
  if (actionCode?.startsWith('ADD')) return 3
  if (actionCode?.startsWith('WAIT')) return 4
  return 5
}

function sortPortfolioItems(list, rows, herdMap, sortMode) {
  const rowMap = new Map(rows.map((row) => [row.ticker, row]))
  return [...list].sort((a, b) => {
    const aHerd = herdMap[a.ticker]
    const bHerd = herdMap[b.ticker]
    const aScore = Number(aHerd?.herdV4 ?? aHerd?.herdScore ?? 50)
    const bScore = Number(bHerd?.herdV4 ?? bHerd?.herdScore ?? 50)

    if (sortMode === 'herdLow') return aScore - bScore
    if (sortMode === 'herdHigh') return bScore - aScore
    if (sortMode === 'weight') {
      const aWeight = Number(rowMap.get(a.ticker)?.currentWeight ?? 0)
      const bWeight = Number(rowMap.get(b.ticker)?.currentWeight ?? 0)
      return bWeight - aWeight
    }

    const priorityDiff = actionPriority(aHerd?.signal) - actionPriority(bHerd?.signal)
    if (priorityDiff !== 0) return priorityDiff

    const aAction = Number(aHerd?.actionScore ?? 0)
    const bAction = Number(bHerd?.actionScore ?? 0)
    if (bAction !== aAction) return bAction - aAction

    return a.ticker.localeCompare(b.ticker)
  })
}

function refreshResultText(priceRes, herdRes, spyRes) {
  const done = []
  const failed = []

  if (priceRes.status === 'fulfilled') done.push('현재가 갱신')
  else failed.push('가격')

  if (herdRes.status === 'fulfilled') done.push('HERD 조회')
  else failed.push('HERD')

  if (spyRes.status === 'fulfilled') done.push('SPY 갱신')
  else failed.push('SPY')

  if (done.length === 0) return '새로고침 실패'
  if (failed.length > 0) return `${done.join(' · ')} · ${failed.join('/')} 실패`
  return done.join(' · ')
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

/** 보유 수량 포맷: 정수는 12주, 소수는 12.3456주 */
function fmtShares(value) {
  if (value == null) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('ko-KR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  })}주`
}

function fmtWeightGap(row) {
  if (!row) return ''
  const gap = row.targetWeight - row.currentWeight
  if (Math.abs(gap) < 0.05) return '목표 근처'
  return gap > 0
    ? `목표까지 ${gap.toFixed(1)}%p`
    : `목표 초과 ${Math.abs(gap).toFixed(1)}%p`
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

/** 차트 X축 날짜 포맷: 2026-06-30 → 6/30 */
function fmtAxisDate(dateStr) {
  const d = new Date(dateStr)
  return Number.isNaN(d.getTime()) ? dateStr : `${d.getMonth() + 1}/${d.getDate()}`
}

function normalizeHistoryPoint(point) {
  const investedValue = point.invested_value ?? point.investedValue ?? point.totalValue ?? point.total_value ?? 0
  const cashBalance = point.cash_balance ?? point.cashBalance ?? 0
  const totalAssetValue = point.total_asset_value ?? point.totalAssetValue ?? point.totalValue ?? point.total_value ?? 0
  return {
    date: point.date,
    investedValue: Number(investedValue),
    cashBalance: Number(cashBalance),
    totalAssetValue: Number(totalAssetValue),
    totalReturnPct: point.total_return_pct ?? point.totalReturnPct ?? null,
  }
}

function currentAssetPoint(summary, cashBalance) {
  if (!summary) return null

  const investedValue = Number(summary.invested_value ?? 0)
  const cash = Number(summary.cash_balance ?? cashBalance ?? 0)
  const totalAssetValue = Number(
    summary.total_asset_value ?? summary.total_value ?? investedValue + cash
  )
  if (!Number.isFinite(totalAssetValue) || totalAssetValue <= 0) return null

  return {
    date: formatInputDate(),
    investedValue: Number.isFinite(investedValue) ? investedValue : 0,
    cashBalance: Number.isFinite(cash) ? cash : 0,
    totalAssetValue,
    totalReturnPct: summary.total_return_pct ?? null,
  }
}

function mergeCurrentAssetPoint(history, currentPoint) {
  if (!currentPoint) return history

  const next = [...history]
  const sameDateIndex = next.findIndex((point) => point.date === currentPoint.date)
  if (sameDateIndex >= 0) {
    next[sameDateIndex] = { ...next[sameDateIndex], ...currentPoint }
  } else {
    next.push(currentPoint)
  }

  return next.sort((a, b) => new Date(a.date) - new Date(b.date))
}

function AssetHistoryTooltip({ active, payload, label, displayAmount }) {
  if (!active || !payload?.length) return null
  const date = new Date(label)
  const dateText = Number.isNaN(date.getTime())
    ? label
    : date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
  const row = payload[0]?.payload

  return (
    <div className={styles.assetTooltip}>
      <div className={styles.assetTooltipDate}>{dateText}</div>
      <div className={styles.assetTooltipRow}>
        <span>총자산</span>
        <strong>{displayAmount(row?.totalAssetValue)}</strong>
      </div>
      <div className={styles.assetTooltipRow}>
        <span>주식</span>
        <strong>{displayAmount(row?.investedValue)}</strong>
      </div>
      <div className={styles.assetTooltipRow}>
        <span>현금</span>
        <strong>{displayAmount(row?.cashBalance)}</strong>
      </div>
    </div>
  )
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
  return score == null ? 'var(--text-1)' : scoreColor(score)
}

/** HERD 점수 → 단계명 (히스토리 통계용) */
function scoreToStage(score) {
  return stageLabelFromScore(score, true)
}

/** points 배열에서 최근 N일 평균 점수 반환 */
function averageScoreForLastDays(points, days, fallbackScore = null) {
  if (!points?.length) return null
  const now = new Date()
  const cutoff = new Date(now)
  cutoff.setDate(cutoff.getDate() - days)

  const values = []
  for (const p of points) {
    const pointDate = new Date(`${p.date}T00:00:00`)
    if (Number.isNaN(pointDate.getTime())) continue
    if (pointDate >= cutoff && pointDate <= now && p.score != null) {
      values.push(Number(p.score))
    }
  }

  if (values.length === 0) {
    const latest = points[points.length - 1]
    const score = fallbackScore ?? latest?.score
    return score == null ? null : { score }
  }

  const score = values.reduce((sum, v) => sum + v, 0) / values.length
  return { score }
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
  const [spyStatsHistory, setSpyStatsHistory] = useState([])
  const [spyHistoryPeriod, setSpyHistoryPeriod] = useState('3y')
  const [spyHistoryLoading, setSpyHistoryLoading] = useState(false)
  const [spyTab,         setSpyTab]         = useState('overview')
  /*
   * SPY 데이터 ref 캐시 — React 18 Strict Mode가 effect를 cleanup → 재실행할 때
   * state는 초기화되지만 ref는 유지된다. 두 번째 실행에서 ref 값을 즉시 state에 반영.
   */
  const spyDataCache    = useRef(null)
  const spyHistoryCache = useRef({})
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  const [modalTicker,    setModalTicker]    = useState(null)
  const [deletingTicker, setDeletingTicker] = useState(null)
  const [exchangeRate,   setExchangeRate]   = useState(null)
  const [refreshing,     setRefreshing]     = useState(false)
  const [refreshNotice,  setRefreshNotice]  = useState(null)
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
  const [portfolioSort,  setPortfolioSort]  = useState(
    () => localStorage.getItem(CACHE_KEY_PORTFOLIO_SORT) || 'action'
  )
  const [targetWeights,  setTargetWeights]  = useState(() => readTargetWeights())
  const [cashBalance,    setCashBalance]    = useState(0)
  const [cashDraft,      setCashDraft]      = useState('')
  const [cashSaving,     setCashSaving]     = useState(false)
  const [assetPanelOpen, setAssetPanelOpen] = useState(false)
  const [assetHistoryPeriod, setAssetHistoryPeriod] = useState('year')
  const [assetHistory,   setAssetHistory]   = useState([])
  const [assetHistoryLoading, setAssetHistoryLoading] = useState(false)
  const [assetHistoryError, setAssetHistoryError] = useState(null)
  const [signalLogs,     setSignalLogs]     = useState([])
  const refreshNoticeTimer = useRef(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* ── 포트폴리오 데이터 로딩 (캐시 우선) ── */
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    if (ensureDashboardCacheVersion()) {
      setLastUpdated(null)
    }
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

      getCashBalance()
        .then((res) => {
          const amount = Number(res.data?.data?.cashAmount ?? 0)
          setCashBalance(amount)
          setCashDraft(amount > 0 ? String(amount) : '')
          setSummary(prev => prev
            ? {
                ...prev,
                cash_balance: amount,
                total_value: Number(prev.invested_value ?? prev.total_value ?? 0) + amount,
                total_asset_value: Number(prev.invested_value ?? prev.total_value ?? 0) + amount,
              }
            : prev
          )
        })
        .catch(() => {
          setCashBalance(0)
        })
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchAssetHistory = useCallback(async () => {
    setAssetHistoryLoading(true)
    setAssetHistoryError(null)
    try {
      const res = await getPortfolioHistory(assetHistoryPeriod)
      const points = (res.data?.data?.points ?? []).map(normalizeHistoryPoint)
      setAssetHistory(points)
    } catch {
      setAssetHistoryError('자산 히스토리를 불러올 수 없습니다.')
    } finally {
      setAssetHistoryLoading(false)
    }
  }, [assetHistoryPeriod])

  useEffect(() => {
    if (assetPanelOpen) fetchAssetHistory()
  }, [assetPanelOpen, fetchAssetHistory])

  useEffect(() => { fetchData() }, [fetchData])

  useEffect(() => {
    const syncSignalLogs = () => {
      getSignalJournal()
        .then((res) => setSignalLogs(res.data?.data ?? []))
        .catch(() => setSignalLogs([]))
    }
    syncSignalLogs()
    window.addEventListener('focus', syncSignalLogs)
    return () => {
      window.removeEventListener('focus', syncSignalLogs)
    }
  }, [])

  useEffect(() => () => {
    if (refreshNoticeTimer.current) clearTimeout(refreshNoticeTimer.current)
  }, [])

  /*
   * SPY 배너 — 포트폴리오 로딩과 완전히 분리.
   * ref 캐시(Strict Mode 대응) → localStorage 캐시 → API 호출 순서로 처리.
   * HERD 점수 + 선택 기간 히스토리 동시 로딩.
   * Overview 통계는 1년 전 비교가 필요하므로 3Y 히스토리를 기준 데이터로 유지한다.
   */
  useEffect(() => {
    const historyKey = spyHistoryCacheKey(spyHistoryPeriod)
    const herdCached = spyDataCache.current ?? readCache(CACHE_KEY_SPY)
    const rawHistoryCached =
      spyHistoryCache.current[spyHistoryPeriod] ??
      readCache(historyKey)
    const historyCached =
      isUsableSpyHistoryCache(spyHistoryPeriod, rawHistoryCached) ? rawHistoryCached : null

    if (herdCached) {
      spyDataCache.current = herdCached
      setSpyData(herdCached)
    }
    if (historyCached) {
      spyHistoryCache.current[spyHistoryPeriod] = historyCached
      setSpyHistory(historyCached)
      setSpyHistoryLoading(false)
      if (spyHistoryPeriod === '3y') setSpyStatsHistory(historyCached)
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
      setSpyHistoryLoading(true)
      setSpyHistory([])
      getSpyHerdHistory(spyHistoryPeriod)
        .then((res) => {
          const points = res.data?.data?.points ?? []
          spyHistoryCache.current[spyHistoryPeriod] = points
          setSpyHistory(points)
          writeCache(historyKey, points)
          if (spyHistoryPeriod === '3y') {
            setSpyStatsHistory(points)
          }
        })
        .catch(() => { /* 히스토리 실패 시 Timeline 탭 빈 상태 유지 */ })
        .finally(() => { setSpyHistoryLoading(false) })
    }
  }, [spyHistoryPeriod])

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
   * 수동 새로고침 — yfinance 현재가 + DB HERD 데이터를 재조회 후 캐시 갱신.
   * getPortfolio()와 SPY 3년 히스토리는 제외한다.
   * 종목 목록은 추가/삭제 시에만 바뀌고, 히스토리는 최초 로딩 캐시로 충분하다.
   */
  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    if (refreshNoticeTimer.current) clearTimeout(refreshNoticeTimer.current)
    setRefreshNotice('현재가 조회 · HERD DB 조회 · SPY 확인 중')
    try {
      const [priceRes, herdRes, spyRes] = await Promise.allSettled([
        getPortfolioRealtime(),
        getPortfolioHerd(),
        getStockHerd('SPY'),
      ])

      if (priceRes.status === 'fulfilled') {
        const data = normalizePortfolioSummary(priceRes.value.data?.data ?? null)
        if (data) {
          data.cash_balance = cashBalance
          data.total_value = Number(data.invested_value ?? data.total_value ?? 0) + Number(cashBalance ?? 0)
          data.total_asset_value = data.total_value
        }
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

      /* 하나라도 성공했을 때만 헤더 "업데이트 · 오후 X:XX" 기준 갱신 */
      if ([priceRes, herdRes, spyRes].some((res) => res.status === 'fulfilled')) {
        setLastUpdated(saveCacheTime())
      }
      setRefreshNotice(refreshResultText(priceRes, herdRes, spyRes))
      refreshNoticeTimer.current = setTimeout(() => {
        setRefreshNotice(null)
      }, 3200)
    } finally {
      setRefreshing(false)
    }
  }, [cashBalance])

  const handleCashSave = useCallback(async () => {
    const amount = Number(cashDraft || 0)
    if (!Number.isFinite(amount) || amount < 0 || cashSaving) return

    setCashSaving(true)
    try {
      const res = await updateCashBalance(amount)
      const saved = Number(res.data?.data?.cashAmount ?? amount)
      setCashBalance(saved)
      setCashDraft(saved > 0 ? String(saved) : '')
      setSummary(prev => {
        if (!prev) return prev
        const investedValue = Number(prev.invested_value ?? prev.total_value ?? 0)
        const next = {
          ...prev,
          cash_balance: saved,
          total_value: investedValue + saved,
          total_asset_value: investedValue + saved,
        }
        writeCache(CACHE_KEY_REALTIME, next)
        return next
      })
      if (assetPanelOpen) fetchAssetHistory()
    } finally {
      setCashSaving(false)
    }
  }, [cashDraft, cashSaving, assetPanelOpen, fetchAssetHistory])

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

  function handlePortfolioSortChange(mode) {
    setPortfolioSort(mode)
    localStorage.setItem(CACHE_KEY_PORTFOLIO_SORT, mode)
  }

  const spyScore = spyData?.herdV4 ?? spyData?.herdScore ?? 50
  const spyStage = spyData?.herdStage ?? 'Calm'

  /* 히스토리 기준 평균 통계 (Overview 탭) */
  const d1AvgPoint = useMemo(
    () => averageScoreForLastDays(spyStatsHistory, 1, spyScore),
    [spyStatsHistory, spyScore]
  )
  const m1AvgPoint = useMemo(
    () => averageScoreForLastDays(spyStatsHistory, 30, spyScore),
    [spyStatsHistory, spyScore]
  )
  const y1AvgPoint = useMemo(
    () => averageScoreForLastDays(spyStatsHistory, 365, spyScore),
    [spyStatsHistory, spyScore]
  )

  const signalJournalSummary = useMemo(
    () => summarizeSignalJournal(signalLogs),
    [signalLogs]
  )

  const recentSignalLogs = useMemo(
    () => signalLogs.slice(0, 3),
    [signalLogs]
  )

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
        const newInvestedValue = (prev.invested_value ?? prev.total_value ?? 0) - oldMarketValue + newMarketValue
        const cash = Number(prev.cash_balance ?? cashBalance ?? 0)
        const oldStock       = portfolio.find(p => p.ticker === ticker)
        const oldCost        = (oldStock?.avgPrice ?? 0) * (oldStock?.quantity ?? 0)
        const newTotalCost   = (prev.total_cost ?? 0) - oldCost + newAvgPrice * newQty
        const newTotalReturnPct = newTotalCost > 0
          ? (newInvestedValue - newTotalCost) / newTotalCost * 100
          : 0

        const next = {
          ...prev,
          stocks:           updatedStocks,
          invested_value:   newInvestedValue,
          total_value:      newInvestedValue + cash,
          total_asset_value: newInvestedValue + cash,
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
  }, [modalTicker, priceMap, portfolio, fetchData, cashBalance])

  const modalStock = portfolio.find((p) => p.ticker === modalTicker)
  const rows = useMemo(
    () => portfolioRows(portfolio, summary, herdMap, targetWeights),
    [portfolio, summary, herdMap, targetWeights]
  )
  const sortedPortfolio = useMemo(
    () => sortPortfolioItems(portfolio, rows, herdMap, portfolioSort),
    [portfolio, rows, herdMap, portfolioSort]
  )
  const rebalanceRows = useMemo(() => rebalanceIdeas(rows), [rows])
  const actionQueueCards = useMemo(() => {
    const rowMap = new Map(rows.map((row) => [row.ticker, row]))
    return sortedPortfolio
      .map((item) => {
        const herd = herdMap[item.ticker]
        const row = rowMap.get(item.ticker)
        if (!herd || !row) return null
        const action = buildPositionAction(herd, row)
        const score = Math.round(herd.herdV4 ?? herd.herdScore ?? 0)
        const stage = herd.herdStage?.startsWith('Herd ')
          ? herd.herdStage.slice(5)
          : herd.herdStage ?? 'Calm'
        return {
          ticker: item.ticker,
          herd,
          row,
          action,
          score,
          stage,
          price: priceMap[item.ticker],
          priority: queuePriority(action.code),
        }
      })
      .filter(Boolean)
      .sort((a, b) => {
        if (a.priority !== b.priority) return a.priority - b.priority
        return Number(b.herd.actionScore ?? 0) - Number(a.herd.actionScore ?? 0)
      })
      .slice(0, 3)
  }, [sortedPortfolio, rows, herdMap, priceMap])
  const assetHistoryWithCurrent = useMemo(
    () => mergeCurrentAssetPoint(assetHistory, currentAssetPoint(summary, cashBalance)),
    [assetHistory, summary, cashBalance]
  )
  const assetChartHistory = assetHistoryWithCurrent
  const assetLatest = assetChartHistory.length > 0 ? assetChartHistory[assetChartHistory.length - 1] : null
  const assetFirst = assetChartHistory.length > 0 ? assetChartHistory[0] : null
  const assetStartValue = assetFirst?.totalAssetValue ?? null
  const assetPeak = assetChartHistory.length > 0
    ? assetChartHistory.reduce((best, point) =>
        Number(point.totalAssetValue) > Number(best.totalAssetValue) ? point : best
      , assetChartHistory[0])
    : null
  const assetStartPct = assetStartValue && assetLatest?.totalAssetValue
    ? (assetLatest.totalAssetValue / assetStartValue - 1) * 100
    : null
  const assetDrawdownPct = assetPeak?.totalAssetValue && assetLatest?.totalAssetValue
    ? (assetLatest.totalAssetValue / assetPeak.totalAssetValue - 1) * 100
    : null
  const assetValues = assetChartHistory.map((p) => p.totalAssetValue)
  if (assetStartValue) assetValues.push(assetStartValue)
  const assetMin = assetValues.length > 0 ? Math.min(...assetValues) : 0
  const assetMax = assetValues.length > 0 ? Math.max(...assetValues) : 1000
  const assetPadding = (assetMax - assetMin) * 0.08 || 100
  const assetYDomain = [Math.max(0, assetMin - assetPadding), assetMax + assetPadding]
  const assetPeriodLabel = ASSET_HISTORY_PERIODS.find((p) => p.value === assetHistoryPeriod)?.label ?? '선택 기간'
  const assetStartLabel = assetFirst?.date ? fmtAxisDate(assetFirst.date) : '—'

  function handleTargetWeightChange(ticker, value) {
    const next = { ...targetWeights }
    if (value === '') {
      delete next[ticker]
    } else {
      const n = Number(value)
      if (!Number.isFinite(n)) return
      next[ticker] = String(Math.min(100, Math.max(0, n)))
    }
    setTargetWeights(next)
    writeTargetWeights(next)
  }

  return (
    <div className={styles.dashboardShell}>

      {/* ── 페이지 헤더 ── */}
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>내 포트폴리오</h1>
          <p className={styles.pageSubtitle}>시장 흐름과 보유 종목의 행동 대기열을 먼저 확인합니다.</p>
        </div>
        <div className={styles.headerActions}>
          {/* 마지막 캐시 저장 시각 — localStorage 'hs_cache_time' 기준 */}
          {lastUpdated && (
            <span className={styles.updateTime}>
              업데이트 · {fmtTime(lastUpdated)}
            </span>
          )}
          {refreshNotice && (
            <span className={styles.refreshNotice}>
              {refreshNotice}
            </span>
          )}
          <button
            className={styles.btnRefresh}
            onClick={handleRefresh}
            disabled={refreshing || loading}
            title={REFRESH_SCOPE_TITLE}
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

      <div className={styles.commandFrame}>
        <div className={styles.commandFrameTop}>
          <div>
            <span>Signal Command Center</span>
            <strong>현재 시장 신호</strong>
          </div>
          <div className={styles.commandFrameMeta}>
            <span>{lastUpdated ? `업데이트 · ${fmtTime(lastUpdated)}` : '업데이트 대기'}</span>
            <button type="button" onClick={() => navigate('/herd-lab')}>
              리포트 보기
            </button>
          </div>
        </div>

        {/* ── S&P500 HERD 시장 무대 ── */}
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
                  <HerdDots score={spyScore} fill dotCount={84} />
                  <div className={styles.bannerAnimLabel}>
                    <span>← Flee · 군중 이탈</span>
                    <span>Rush · 군중 밀집 →</span>
                  </div>
                  <div className={styles.bannerSpectrumOverlay}>
                    <SpectrumBar score={spyScore} height={3} />
                  </div>
                </div>
                <div className={styles.bannerHistStats}>
                  <BannerStat label="1일 평균" point={d1AvgPoint} />
                  <BannerStat label="1달 평균" point={m1AvgPoint} />
                  <BannerStat label="1년 평균" point={y1AvgPoint} />
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
                <div className={styles.bannerPeriodTabs}>
                  {HISTORY_PERIODS.map((p) => (
                    <button
                      key={p.value}
                      className={`${styles.bannerPeriodTab} ${spyHistoryPeriod === p.value ? styles.bannerPeriodTabActive : ''}`}
                      onClick={() => setSpyHistoryPeriod(p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                {spyHistoryLoading ? (
                  <div className={styles.bannerTimelineEmpty}>로딩 중…</div>
                ) : spyHistory.length === 0 ? (
                  <div className={styles.bannerTimelineEmpty}>데이터 없음</div>
                ) : (
                  <HerdHistoryChart
                    points={spyHistory}
                    currentScore={spyScore}
                    height={190}
                  />
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── 행동 대기열 — 장기투자 관찰 후보를 먼저 보여준다 ── */}
        {!loading && !error && portfolio.length > 0 && (
          <div className={styles.commandQueue}>
            <div className={styles.commandQueueHead}>
              <span>Action Queue</span>
              <strong>
                {actionQueueCards.length > 0
                  ? `${actionQueueCards.length}개 핵심 후보`
                  : '강한 행동 신호 없음'}
              </strong>
            </div>
            <div className={styles.commandQueueList}>
              {actionQueueCards.length > 0 ? (
                actionQueueCards.map((card) => {
                  const actionColor = card.action.muted
                    ? 'var(--calm)'
                    : signalStyle(card.herd.signal).color
                  const cardTone = card.action.code.startsWith('SELL') || card.action.code.startsWith('REDUCE')
                    ? styles.commandTicketSell
                    : card.action.code.startsWith('ADD') || card.action.code.startsWith('BUY')
                      ? styles.commandTicketBuy
                      : styles.commandTicketHold

                  return (
                  <button
                    key={card.ticker}
                    type="button"
                    className={`${styles.commandTicket} ${cardTone}`}
                    onClick={() => navigate(`/stock/${card.ticker}`)}
                  >
                    <span className={styles.commandActionIcon} style={{ color: actionColor }}>
                      {card.action.code.startsWith('SELL') || card.action.code.startsWith('REDUCE') ? '↓' : card.action.code.startsWith('HOLD') || card.action.code.startsWith('WAIT') ? '○' : '↑'}
                    </span>
                    <div className={styles.commandTicketMain}>
                      <strong style={{ color: actionColor }}>{card.action.code}</strong>
                      <span>{card.ticker}</span>
                      <em>{card.stage} · HERD {card.score}</em>
                    </div>
                    <div className={styles.commandTicketMeta}>
                      <span>{card.action.text}</span>
                      <small>{card.row.currentWeight.toFixed(1)}% / {card.row.targetWeight.toFixed(1)}%</small>
                      {card.price && (
                        <small style={{ color: pctColor(card.price.daily_change_pct) }}>
                          오늘 {fmtPct(card.price.daily_change_pct)}
                        </small>
                      )}
                    </div>
                  </button>
                  )
                })
              ) : (
                <div className={styles.commandEmpty}>
                  <strong>현재는 보유와 관찰 구간입니다.</strong>
                  <span>Flee/Rush 또는 목표비중 이탈이 커질 때 대기열에 올라옵니다.</span>
                </div>
              )}
            </div>
          </div>
        )}

        {summary && (
          <div className={styles.portfolioSummaryBar}>
            <div className={styles.summaryMain}>
              <span>포트폴리오 요약</span>
              <strong>{displayAmount(summary.total_value)}</strong>
              <em style={{ color: pctColor(summary.total_return_pct) }}>
                {displayPnl((summary.invested_value ?? summary.total_value) - summary.total_cost)}
                {' '}
                {fmtPct(summary.total_return_pct)}
              </em>
            </div>
            <div className={styles.summaryMetric}>
              <span>주식 평가액</span>
              <strong>{displayAmount(summary.invested_value ?? summary.total_value)}</strong>
            </div>
            <div className={styles.summaryMetric}>
              <span>현금</span>
              <strong>{displayAmount(summary.cash_balance ?? cashBalance)}</strong>
            </div>
            <div className={styles.summaryMetric}>
              <span>오늘 등락</span>
              <strong style={{ color: pctColor(summary.daily_change_pct) }}>
                {fmtPct(summary.daily_change_pct)}
              </strong>
            </div>
            <div className={styles.summaryActions}>
              <div className={styles.currencyToggle}>
                <button
                  className={`${styles.currencyBtn} ${currencyMode === 'KRW' ? styles.currencyBtnActive : ''}`}
                  onClick={() => handleCurrencyToggle('KRW')}
                >
                  ₩
                </button>
                <button
                  className={`${styles.currencyBtn} ${currencyMode === 'USD' ? styles.currencyBtnActive : ''}`}
                  onClick={() => handleCurrencyToggle('USD')}
                >
                  $
                </button>
              </div>
              <button
                type="button"
                className={styles.ledgerHistoryBtn}
                onClick={() => setAssetPanelOpen(open => !open)}
              >
                {assetPanelOpen ? '히스토리 닫기' : '히스토리'}
              </button>
            </div>
          </div>
        )}
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

      {/* ── 포트폴리오 세부 패널 ── */}
      {summary && (
        <>
          {editMode && (
            <div className={styles.portfolioEditPanel}>
              <div className={styles.portfolioEditInfo}>
                <span>포트폴리오 설정</span>
                <strong>현금 보유액</strong>
                <em>총자산과 목표 비중 계산에 함께 반영됩니다.</em>
              </div>
              <div className={styles.cashEditControl}>
                <div className={styles.cashInputRow}>
                  <span className={styles.cashPrefix}>$</span>
                  <input
                    className={styles.cashInput}
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    value={cashDraft}
                    onChange={(e) => setCashDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCashSave()
                    }}
                    placeholder="0.00"
                    aria-label="현금 보유액"
                  />
                </div>
                <button
                  type="button"
                  className={styles.cashSaveBtn}
                  onClick={handleCashSave}
                  disabled={cashSaving}
                >
                  {cashSaving ? '저장 중…' : '현금 저장'}
                </button>
              </div>
            </div>
          )}

          {assetPanelOpen && (
            <div className={styles.assetPanel}>
              <div className={styles.assetPanelHeader}>
                <div>
                  <div className={styles.assetPanelLabel}>Asset History · {assetPeriodLabel}</div>
                  <div className={styles.assetPanelTitle}>
                    {assetLatest ? displayAmount(assetLatest.totalAssetValue) : displayAmount(summary.total_value)}
                  </div>
                  <div className={styles.assetPanelSub}>
                    입출금 포함 총자산 흐름 · 기간 시작 {assetStartLabel}
                    {assetFirst?.totalAssetValue != null ? ` · ${displayAmount(assetFirst.totalAssetValue)}` : ''}
                  </div>
                </div>
                <div className={styles.assetPeriodToggle}>
                  {ASSET_HISTORY_PERIODS.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      className={`${styles.assetPeriodBtn} ${assetHistoryPeriod === p.value ? styles.assetPeriodBtnActive : ''}`}
                      onClick={() => setAssetHistoryPeriod(p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className={styles.assetStats}>
                <div>
                  <span>총자산 변화</span>
                  <strong style={{ color: pctColor(assetStartPct) }}>{fmtPct(assetStartPct)}</strong>
                  <em>입출금 포함</em>
                </div>
                <div>
                  <span>고점 대비</span>
                  <strong style={{ color: pctColor(assetDrawdownPct) }}>{fmtPct(assetDrawdownPct)}</strong>
                  <em>현재 총자산 기준</em>
                </div>
                <div>
                  <span>현재 현금</span>
                  <strong>{displayAmount(summary.cash_balance ?? cashBalance)}</strong>
                  <em>총자산에 포함</em>
                </div>
                <div>
                  <span>주식 평가액</span>
                  <strong>{displayAmount(summary.invested_value ?? summary.total_value)}</strong>
                  <em>보유 종목 평가</em>
                </div>
              </div>

              {assetHistoryLoading && (
                <div className={styles.assetState}>히스토리 로딩 중…</div>
              )}
              {!assetHistoryLoading && assetHistoryError && (
                <div className={styles.assetState}>{assetHistoryError}</div>
              )}
              {!assetHistoryLoading && !assetHistoryError && assetChartHistory.length === 0 && (
                <div className={styles.assetState}>아직 자산 히스토리가 없습니다.</div>
              )}
              {!assetHistoryLoading && !assetHistoryError && assetChartHistory.length > 0 && (
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart
                    data={assetChartHistory}
                    margin={{ top: 12, right: 14, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="4 6" stroke="var(--border)" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={fmtAxisDate}
                      tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                      axisLine={false}
                      tickLine={false}
                      tickMargin={8}
                    />
                    <YAxis
                      domain={assetYDomain}
                      tickFormatter={(v) => v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`}
                      tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                      axisLine={false}
                      tickLine={false}
                      width={56}
                    />
                    <Tooltip content={<AssetHistoryTooltip displayAmount={displayAmount} />} />
                    {summary.total_cost != null && (
                      <ReferenceLine
                        y={summary.total_cost}
                        stroke="rgba(163, 170, 184, 0.55)"
                        strokeDasharray="4 4"
                      />
                    )}
                    {assetStartValue != null && (
                      <ReferenceLine
                        y={assetStartValue}
                        stroke="rgba(59, 130, 246, 0.45)"
                        strokeDasharray="5 5"
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="totalAssetValue"
                      stroke="var(--flee)"
                      strokeWidth={2.5}
                      dot={assetChartHistory.length === 1
                        ? { r: 5, fill: 'var(--flee)', strokeWidth: 0 }
                        : false
                      }
                      activeDot={{ r: 5, strokeWidth: 0 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          )}

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

          {signalJournalSummary.totalCount > 0 && (
            <div className={styles.journalOverview}>
              <div className={styles.journalOverviewHead}>
                <div>
                  <span>판단 기록</span>
                  <strong>{formatJournalCount(signalJournalSummary.totalCount)}</strong>
                </div>
                <button
                  type="button"
                  className={styles.journalOverviewLink}
                  onClick={() => navigate('/journal')}
                >
                  전체 기록 보기
                </button>
              </div>
              <div className={styles.journalOverviewStats}>
                <div>
                  <span>매수 총액</span>
                  <strong>{formatJournalAmount(signalJournalSummary.buyAmount) ?? '$0'}</strong>
                  <em>{formatJournalCount(signalJournalSummary.buyCount)}</em>
                </div>
                <div>
                  <span>익절 총액</span>
                  <strong>{formatJournalAmount(signalJournalSummary.sellAmount) ?? '$0'}</strong>
                  <em>{formatJournalCount(signalJournalSummary.sellCount)}</em>
                </div>
                <div>
                  <span>평균 익절률</span>
                  <strong>
                    {signalJournalSummary.hasProfitData
                      ? formatJournalProfit(signalJournalSummary.avgProfitPct)
                      : '—'}
                  </strong>
                  <em>익절 기록 기준</em>
                </div>
              </div>
              {recentSignalLogs.length > 0 && (
                <div className={styles.journalRecentList}>
                  {recentSignalLogs.map((log) => (
                    <button
                      key={log.id}
                      type="button"
                      className={styles.journalRecentItem}
                      onClick={() => navigate(`/stock/${log.ticker}`)}
                    >
                      <strong>{log.ticker}</strong>
                      <span>{log.actionLabel ?? log.actionType ?? '기록'}</span>
                      <em>{formatJournalAmount(log.amount) ?? `HERD ${log.herdScore ?? '—'}`}</em>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ── 종목 카드 그리드 ── */}
      {!loading && !error && portfolio.length > 0 && (
        <>
          <div className={styles.sectionRow}>
            <div className={styles.sectionTitle}>보유 종목 · {portfolio.length}</div>
            <div className={styles.sortTabs} aria-label="보유 종목 정렬">
              {PORTFOLIO_SORT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  className={`${styles.sortTab} ${portfolioSort === option.value ? styles.sortTabActive : ''}`}
                  onClick={() => handlePortfolioSortChange(option.value)}
                  type="button"
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.holdingsTable}>
            <div className={styles.holdingsHeader}>
              <span>종목</span>
              <span>보유 비중</span>
              <span>평가금액</span>
              <span>수익률</span>
              <span>HERD</span>
              <span>신호</span>
            </div>
            {sortedPortfolio.map((item) => {
              const row       = rows.find((r) => r.ticker === item.ticker)
              const herd      = herdMap[item.ticker]
              const stage     = herd?.herdStage ?? 'Calm'
              const color     = stageColor(stage)
              const badge     = badgeStyle(stage)
              const signal    = signalStyle(herd?.signal)
              const stageName = stage.startsWith('Herd ') ? stage.slice(5) : stage
              const herdScore = herd ? Math.round(herd.herdV4 ?? herd.herdScore) : null
              const positionAction = herd ? buildPositionAction(herd, row) : null
              const actionColor = positionAction?.muted ? 'var(--calm)' : signal.color

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
                  className={`${styles.holdingRow} ${editMode ? styles.holdingRowEdit : ''}`}
                  onClick={editMode ? undefined : () => navigate(`/stock/${item.ticker}`)}
                  style={{ opacity: isDeleting ? 0.4 : 1 }}
                >
                  <div className={styles.cardStripe} style={{ background: color, color }} />

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

                  <div className={styles.holdingStockCell}>
                    <StockAvatar
                      ticker={item.ticker}
                      logoUrl={herd?.logoUrl}
                      tone={badge}
                      size="lg"
                    />
                    <div className={styles.holdingStockText}>
                      <strong>{item.ticker}</strong>
                      <span style={{ color }}>
                        {stageName}
                        {herdScore != null ? ` · HERD ${herdScore}` : ''}
                      </span>
                      {shouldShowQuality(herd) && (
                        <em style={{ color: qualityColor(herd.qualityLevel) }}>
                          {qualityWarningText(herd)}
                        </em>
                      )}
                    </div>
                  </div>

                  <div className={styles.holdingMetric}>
                    <span>{row ? `${row.currentWeight.toFixed(1)}%` : '—'}</span>
                    <em>{row ? `목표 ${row.targetWeight.toFixed(1)}%` : '목표 —'}</em>
                    {row && <small>{fmtWeightGap(row)}</small>}
                  </div>

                  <div className={styles.holdingMetric}>
                    <span>{price ? displayAmount(price.market_value) : '—'}</span>
                    <em>{hasAvgPrice ? `보유 ${fmtShares(item.quantity)}` : '수량 미입력'}</em>
                    {hasAvgPrice && <small>평단 {displayAmount(item.avgPrice)}</small>}
                  </div>

                  <div className={styles.holdingMetric}>
                    <span style={{ color: pctColor(price?.return_pct) }}>
                      {price ? fmtPct(price.return_pct) : '—'}
                    </span>
                    <em style={{ color: pctColor(price?.return_pct) }}>
                      {pnlUsd != null ? displayPnl(pnlUsd) : '평단 필요'}
                    </em>
                    {price && (
                      <small style={{ color: pctColor(price.daily_change_pct) }}>
                        오늘 {fmtPct(price.daily_change_pct)}
                      </small>
                    )}
                  </div>

                  <div className={styles.holdingHerdCell}>
                    {herd ? (
                      <>
                        <strong style={{ color }}>{herdScore}</strong>
                        <span style={{ color }}>{stageName}</span>
                        {formatSignalDuration(herd) && <em>{formatSignalDuration(herd)}</em>}
                      </>
                    ) : (
                      <span className={styles.cardDash}>—</span>
                    )}
                  </div>

                  <div className={styles.holdingActionCell}>
                    {herd ? (
                      <>
                        <strong style={{ color: actionColor }}>{positionAction.code}</strong>
                        <span>{positionAction.text}</span>
                        <em>{positionAction.basis}</em>
                      </>
                    ) : (
                      <span className={styles.cardDash}>—</span>
                    )}
                  </div>

                  {editMode && (
                    <div className={styles.holdingEditTray} onClick={e => e.stopPropagation()}>
                      <button
                        className={styles.cardInputBtn}
                        onClick={e => {
                          e.stopPropagation()
                          setModalTicker(item.ticker)
                        }}
                      >
                        {hasAvgPrice ? '평단·수량 수정' : '평단·수량 입력'}
                      </button>
                      {row && (
                        <div className={styles.targetEditRow}>
                          <label className={styles.targetLabel} htmlFor={`target-${item.ticker}`}>
                            목표 비중
                          </label>
                          <div className={styles.targetInputWrap}>
                            <input
                              id={`target-${item.ticker}`}
                              className={styles.targetInput}
                              type="number"
                              min="0"
                              max="100"
                              step="1"
                              value={targetWeights[item.ticker] ?? ''}
                              placeholder={row.targetWeight.toFixed(0)}
                              onChange={e => handleTargetWeightChange(item.ticker, e.target.value)}
                              aria-label={`${item.ticker} 목표 비중`}
                            />
                            <span>%</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
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
