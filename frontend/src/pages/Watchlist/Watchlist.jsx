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

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate }   from 'react-router-dom'
import {
  getWatchlistHerd,
  getStockHerd,
  getSpyHerdHistory,
  removeFromWatchlist,
} from '../../api/herdApi'
import HerdDots  from '../../components/HerdDots/HerdDots'
import HerdHistoryChart from '../../components/HerdHistoryChart/HerdHistoryChart'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import { signalDesc as decisionSignalDesc } from '../../utils/decision'
import { scoreColor, stageLabelFromScore } from '../../utils/herdStage'
import { opportunityRows } from '../../utils/portfolioTools'
import styles    from './Watchlist.module.css'

/* 환경변수에서 API 호스트 추출 — 에러 메시지 표시용 */
const API_HOST = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080')
  .replace(/^https?:\/\//, '')

const HISTORY_PERIODS = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '1y', label: '1Y' },
  { value: '3y', label: '3Y' },
]

const REFRESH_SCOPE_TITLE = '관심종목 HERD DB 조회와 SPY 최신 점수만 갱신합니다. 히스토리는 Timeline 탭에서 별도 조회됩니다.'

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
    case 'rush':    return '군중 밀집 · 적극 익절'
    case 'drift':   return '쏠림 진행 · 일부 익절 고려'
    case 'scatter': return '군중 흩어짐 · 분할 매수'
    case 'flee':    return '군중 이탈 · 적극 매수'
    default:        return '군중 균형 · 보유 유지'
  }
}

/** signal → 배지 배경색 + 텍스트 색 */
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

/** stage → 티커 배지 배경/텍스트 색 */
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

function qualityWarningText(item) {
  const label = item?.qualityLevel === 'LOW' ? '데이터 부족' : '데이터 제한'
  return `${label}${item?.qualityScore != null ? ` · ${item.qualityScore}` : ''}`
}

function formatActionScore(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `강도 ${Math.round(n)}`
}

function formatActionText(item) {
  const action = item?.actionLabel ?? decisionSignalDesc(item?.signal)
  const strength = formatActionScore(item?.actionScore)
  const ratio = Number(item?.actionRatio ?? 0)
  const ratioText = Number.isFinite(ratio) && ratio > 0 ? `${Math.round(ratio * 100)}%` : null
  return [strength, ratioText, action].filter(Boolean).join(' · ')
}

function formatActionBasis(item) {
  const ratio = Number(item?.actionRatio ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return '현재 비중 유지'

  const pct = Math.round(ratio * 100)
  if (item?.signal === 'BUY' || item?.signal === 'ADD') {
    return `목표 투자금 기준 ${pct}% 분할 투입`
  }
  if (item?.signal === 'SELL' || item?.signal === 'REDUCE') {
    return `보유 평가금액 기준 ${pct}% 축소`
  }
  return '현재 비중 유지'
}

function formatActionCode(item) {
  if (!item?.signal) return 'HOLD'
  const ratio = Number(item.actionRatio ?? 0)
  if (!Number.isFinite(ratio) || ratio <= 0) return item.signal
  return `${item.signal} ${Math.round(ratio * 100)}%`
}

/** scoreDate → 한국어 날짜 문자열 */
function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (isNaN(d)) return dateStr
  return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

function fmtScoreDate(dateStr) {
  if (!dateStr) return '—'

  const nowKST = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Seoul' }))
  const pad = (n) => String(n).padStart(2, '0')
  const todayStr = `${nowKST.getFullYear()}-${pad(nowKST.getMonth() + 1)}-${pad(nowKST.getDate())}`
  const ystKST = new Date(nowKST)
  ystKST.setDate(ystKST.getDate() - 1)
  const ystStr = `${ystKST.getFullYear()}-${pad(ystKST.getMonth() + 1)}-${pad(ystKST.getDate())}`

  if (dateStr === todayStr) return '오늘'
  if (dateStr === ystStr) return '어제'

  const d = new Date(dateStr)
  return isNaN(d) ? dateStr : d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

function scoreToColor(score) {
  return score == null ? 'var(--text-1)' : scoreColor(score)
}

function scoreToStage(score) {
  return stageLabelFromScore(score, true)
}

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

export default function Watchlist() {
  const navigate = useNavigate()

  const [watchlist,      setWatchlist]      = useState([])
  const [spyData,        setSpyData]        = useState(null)
  const [spyHistory,     setSpyHistory]     = useState([])
  const [spyStatsHistory, setSpyStatsHistory] = useState([])
  const [spyHistoryPeriod, setSpyHistoryPeriod] = useState('3y')
  const [spyHistoryLoading, setSpyHistoryLoading] = useState(false)
  const [spyTab,         setSpyTab]         = useState('overview')
  const [loading,        setLoading]        = useState(true)
  const [refreshing,     setRefreshing]     = useState(false)
  const [refreshNotice,  setRefreshNotice]  = useState(null)
  const [error,          setError]          = useState(null)
  /* 삭제 중인 ticker — 중복 요청 방지 */
  const [deletingTicker, setDeletingTicker] = useState(null)
  /* SPY 데이터 ref 캐시 — Dashboard와 동일한 StrictMode 대응 */
  const spyDataCache = useRef(null)
  const spyHistoryCache = useRef({})
  const refreshNoticeTimer = useRef(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* 관심 종목 조회 (SPY와 분리) */
  const fetchData = useCallback(async (silent = false) => {
    if (silent) {
      setRefreshing(true)
      if (refreshNoticeTimer.current) clearTimeout(refreshNoticeTimer.current)
      setRefreshNotice('관심종목 HERD 조회 중')
    } else {
      setLoading(true)
    }
    setError(null)
    try {
      const watchlistRes = await getWatchlistHerd().catch(() => null)

      if (watchlistRes) {
        const responseData = watchlistRes.data?.data
        /* API 응답: { stocks: [...], averageScore, totalCount } 또는 배열 */
        const stocks = responseData?.stocks
          ?? (Array.isArray(responseData) ? responseData : [])
        setWatchlist(stocks)
        if (silent) setRefreshNotice('관심종목 HERD 갱신')
      } else {
        setWatchlist([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
        if (silent) setRefreshNotice('관심종목 HERD 조회 실패')
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
      if (silent) {
        refreshNoticeTimer.current = setTimeout(() => {
          setRefreshNotice(null)
        }, 3200)
      }
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])
  useEffect(() => () => {
    if (refreshNoticeTimer.current) clearTimeout(refreshNoticeTimer.current)
  }, [])

  /*
   * SPY 배너 — Dashboard와 동일한 구조.
   * ref 캐시로 StrictMode 이중 실행 시 state 재설정 문제 방지.
   */
  useEffect(() => {
    const historyCached = spyHistoryCache.current[spyHistoryPeriod]

    if (spyDataCache.current && historyCached) {
      setSpyData(spyDataCache.current)
      setSpyHistory(historyCached)
      if (spyHistoryPeriod === '3y') setSpyStatsHistory(historyCached)
      return
    }

    if (!spyDataCache.current) {
      getStockHerd('SPY')
        .then((res) => {
          const data = res.data?.data ?? null
          spyDataCache.current = data
          setSpyData(data)
        })
        .catch(() => { /* SPY 실패 시 배너 기본값(Calm/50) 유지 */ })
    } else {
      setSpyData(spyDataCache.current)
    }

    setSpyHistoryLoading(true)
    setSpyHistory([])
    getSpyHerdHistory(spyHistoryPeriod)
      .then((res) => {
        const points = res.data?.data?.points ?? []
        spyHistoryCache.current[spyHistoryPeriod] = points
        setSpyHistory(points)
        if (spyHistoryPeriod === '3y') setSpyStatsHistory(points)
      })
      .catch(() => { /* 히스토리 실패 시 Timeline 탭 빈 상태 유지 */ })
      .finally(() => setSpyHistoryLoading(false))
  }, [spyHistoryPeriod])

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

  const spyScore = spyData?.herdV4 ?? spyData?.herdScore ?? 50
  const spyStage = spyData?.herdStage ?? 'Calm'
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

  const sortedWatchlist = useMemo(() => (
    watchlist
      .map((item) => opportunityRows([item])[0] ?? item)
      .sort((a, b) => Number(b.opportunityScore ?? 0) - Number(a.opportunityScore ?? 0))
  ), [watchlist])

  const opportunityQueue = useMemo(() => (
    opportunityRows(watchlist)
      .filter((item) => item.signal === 'BUY' || item.signal === 'ADD')
      .slice(0, 5)
  ), [watchlist])

  function shouldShowQuality(item) {
    if (!item?.qualityLabel) return false
    if (item.qualityLevel === 'LIMITED' || item.qualityLevel === 'LOW') return true
    return Number(item.qualityScore ?? 100) < 70
  }

  return (
    <div>

      {/* ── 페이지 헤더 ── */}
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>관심 종목</h1>
        </div>
        <div className={styles.headerActions}>
          {refreshNotice && (
            <span className={styles.refreshNotice}>
              {refreshNotice}
            </span>
          )}
          <button
            className={styles.btnRefresh}
            onClick={() => fetchData(true)}
            disabled={refreshing || loading}
            title={REFRESH_SCOPE_TITLE}
          >
            {refreshing ? '새로고침 중…' : '↻ 새로고침'}
          </button>
          <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
            종목 추가
          </button>
        </div>
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

        <div className={styles.bannerRight}>
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

          {spyTab === 'overview' && (
            <div className={styles.bannerOverview}>
              <div className={styles.bannerAnimBlock}>
                <HerdDots score={spyScore} fill dotCount={60} />
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
                    {spyData ? fmtScoreDate(spyData.scoreDate) : '—'}
                  </div>
                </div>
              </div>
            </div>
          )}

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
          <div className={styles.opportunityPanel}>
            <div className={styles.sectionRow}>
              <div className={styles.sectionTitle}>매수 대기열</div>
              <div className={styles.sectionHint}>Flee/Scatter 우선 · 매수 우선도순</div>
            </div>
            {opportunityQueue.length > 0 ? (
              <div className={styles.opportunityList}>
                {opportunityQueue.map((item, index) => {
                  const signal = signalStyle(item.signal)
                  return (
                    <button
                      key={item.ticker}
                      className={styles.opportunityItem}
                      onClick={() => navigate(`/stock/${item.ticker}`)}
                    >
                      <span>{index + 1}</span>
                      <strong>{item.ticker}</strong>
                      <em>{formatActionCode(item)}</em>
                      <small style={{ color: signal.color }}>
                        {formatActionBasis(item)} · HERD {Math.round(item.herdV4 ?? item.herdScore)}
                      </small>
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className={styles.opportunityEmpty}>
                지금은 추가매수 후보가 없습니다.
              </div>
            )}
          </div>

          <div className={styles.sectionRow}>
            <div className={styles.sectionTitle}>관심 종목 · {watchlist.length}</div>
            <div className={styles.sectionHint}>매수 우선도순</div>
          </div>

          <div className={styles.stockGrid}>
            {sortedWatchlist.map((item) => {
              const color      = stageColor(item.herdStage)
              const badge      = badgeStyle(item.herdStage)
              const signal     = signalStyle(item.signal)
              const stageName  = item.herdStage.startsWith('Herd ')
                ? item.herdStage.slice(5)
                : item.herdStage
              const isDeleting = deletingTicker === item.ticker
              const opportunity = item.opportunityScore ?? opportunityRows([item])[0]?.opportunityScore

              return (
                <div
                  key={item.ticker}
                  className={styles.stockCard}
                  onClick={() => navigate(`/stock/${item.ticker}`)}
                  style={{ opacity: isDeleting ? 0.4 : 1 }}
                >
                  {/* 좌측 HERD 단계 컬러 스트라이프 */}
                  <div className={styles.cardStripe} style={{ background: color, color }} />

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
                        <div className={styles.cardStageName}>
                          {stageName} · 매수 우선도 {Math.round(opportunity)}
                        </div>
                        {shouldShowQuality(item) && (
                          <div
                            className={styles.cardQuality}
                            style={{ color: qualityColor(item.qualityLevel) }}
                          >
                            {qualityWarningText(item)}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className={styles.cardHerd}>
                      <div className={styles.cardHerdNum} style={{ color }}>
                        {Math.round(item.herdV4 ?? item.herdScore)}
                      </div>
                      <div className={styles.cardHerdStage}>{stageName}</div>
                    </div>
                  </div>

                  {/* 카드 하단: 시그널 배지만 (관심 종목은 재무 데이터 없음) */}
                  <div className={styles.cardBottom}>
                    <div className={styles.cardSignalGroup}>
                      <span
                        className={styles.cardSignalBadge}
                        style={{ background: signal.bg, color: signal.color }}
                      >
                        {item.signal}
                      </span>
                      <span className={styles.cardSignalDesc}>
                        {formatActionText(item)}
                      </span>
                    </div>
                    <span className={styles.cardActionBasis}>
                      {formatActionBasis(item)}
                    </span>
                    <span className={styles.cardUpdate}>
                      {formatDate(item.scoreDate)}
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
