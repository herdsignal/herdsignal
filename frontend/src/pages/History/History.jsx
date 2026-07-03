/**
 * History.jsx — 포트폴리오 자산 기록 (/history)
 *
 * 구성:
 *   - 월/년 토글 버튼
 *   - recharts LineChart (총 평가금액 시계열)
 *   - getPortfolioHistory(period) 연동
 */

import { useState, useEffect, useCallback } from 'react'
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
import { getPortfolioHistory, getPortfolioSummary } from '../../api/herdApi'
import styles from './History.module.css'

/* ── 유틸 ─────────────────────────────────── */

/** 날짜 포맷: 2026-06-30 → 6/30 */
function fmtAxisDate(dateStr) {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/** USD 포맷 */
function fmtUSD(value) {
  if (value == null) return '—'
  return `$${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** 퍼센트 포맷 */
function fmtPct(value) {
  if (value == null) return '—'
  const n = Number(value)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

/** 수익률 색상 */
function pctColor(value) {
  if (value == null) return 'var(--text-3)'
  const n = Number(value)
  if (n > 0) return '#22C55E'
  if (n < 0) return 'var(--rush)'
  return 'var(--text-3)'
}

/* ── 커스텀 툴팁 ── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const d = new Date(label)
  const dateStr = d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
  const totalValue    = payload.find((p) => p.dataKey === 'totalValue')?.value
  const totalReturnPct = payload.find((p) => p.dataKey === 'totalReturnPct')?.value

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipDate}>{dateStr}</div>
      <div className={styles.tooltipRow}>
        <span className={styles.tooltipLabel}>평가금액</span>
        <span className={styles.tooltipValue}>{fmtUSD(totalValue)}</span>
      </div>
      {totalReturnPct != null && (
        <div className={styles.tooltipRow}>
          <span className={styles.tooltipLabel}>총 수익률</span>
          <span style={{ color: pctColor(totalReturnPct) }}>
            {fmtPct(totalReturnPct)}
          </span>
        </div>
      )}
    </div>
  )
}

/* ── 컴포넌트 ─────────────────────────────── */

export default function History() {
  const [period,  setPeriod]  = useState('month')
  const [points,  setPoints]  = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [histRes, sumRes] = await Promise.allSettled([
        getPortfolioHistory(period),
        getPortfolioSummary(),
      ])

      if (histRes.status === 'fulfilled') {
        setPoints(histRes.value.data?.data?.points ?? [])
      } else {
        setError('히스토리 데이터를 불러올 수 없습니다.')
      }

      if (sumRes.status === 'fulfilled') {
        setSummary(sumRes.value.data?.data ?? null)
      }
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => { fetchData() }, [fetchData])

  /* 최신 포인트 */
  const latest  = points.length > 0 ? points[points.length - 1] : null
  /* Y축 도메인 — 데이터 최소/최대에 여유 5% 추가 */
  const values  = points.map((p) => p.totalValue)
  const minVal  = values.length > 0 ? Math.min(...values) : 0
  const maxVal  = values.length > 0 ? Math.max(...values) : 1000
  const padding = (maxVal - minVal) * 0.08 || 100
  const yDomain = [Math.max(0, minVal - padding), maxVal + padding]
  const historyInsight = (() => {
    if (points.length < 2) return null
    const first = points[0]
    const peak = points.reduce((best, point) =>
      Number(point.totalValue) > Number(best.totalValue) ? point : best
    , points[0])
    const drawdown = latest?.totalValue && peak?.totalValue
      ? (latest.totalValue / peak.totalValue - 1) * 100
      : null
    const fromStart = first?.totalValue && latest?.totalValue
      ? (latest.totalValue / first.totalValue - 1) * 100
      : null
    return { first, peak, drawdown, fromStart }
  })()

  return (
    <div>

      {/* ── 페이지 헤더 ── */}
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>자산 기록</h1>
        </div>
        {/* 기간 토글 */}
        <div className={styles.periodToggle}>
          <button
            className={`${styles.toggleBtn} ${period === 'month' ? styles.active : ''}`}
            onClick={() => setPeriod('month')}
          >
            1개월
          </button>
          <button
            className={`${styles.toggleBtn} ${period === 'year' ? styles.active : ''}`}
            onClick={() => setPeriod('year')}
          >
            1년
          </button>
        </div>
      </div>

      {/* ── 현재 평가금액 요약 ── */}
      {summary && (
        <div className={styles.metaRow}>
          <div className={styles.metaItem}>
            <div className={styles.metaLabel}>현재 평가금액</div>
            <div className={styles.metaValue}>{fmtUSD(summary.totalValue)}</div>
          </div>
          <div className={styles.metaDivider} />
          <div className={styles.metaItem}>
            <div className={styles.metaLabel}>총 수익률</div>
            <div
              className={styles.metaValue}
              style={{ color: pctColor(summary.totalReturnPct) }}
            >
              {fmtPct(summary.totalReturnPct)}
            </div>
          </div>
          <div className={styles.metaDivider} />
          <div className={styles.metaItem}>
            <div className={styles.metaLabel}>오늘 등락</div>
            <div
              className={styles.metaValue}
              style={{ color: pctColor(summary.dailyChangePct) }}
            >
              {fmtPct(summary.dailyChangePct)}
            </div>
          </div>
        </div>
      )}

      {historyInsight && (
        <div className={styles.insightGrid}>
          <div className={styles.insightCard}>
            <span>시작 대비</span>
            <strong style={{ color: pctColor(historyInsight.fromStart) }}>
              {fmtPct(historyInsight.fromStart)}
            </strong>
            <em>{historyInsight.first.date} 이후</em>
          </div>
          <div className={styles.insightCard}>
            <span>고점 대비</span>
            <strong style={{ color: pctColor(historyInsight.drawdown) }}>
              {fmtPct(historyInsight.drawdown)}
            </strong>
            <em>고점 {fmtUSD(historyInsight.peak.totalValue)}</em>
          </div>
          <div className={styles.insightCard}>
            <span>점검 포인트</span>
            <strong>
              {historyInsight.drawdown != null && historyInsight.drawdown < -8
                ? '리밸런싱 확인'
                : '비중 유지 가능'}
            </strong>
            <em>HERD 신호와 함께 확인</em>
          </div>
        </div>
      )}

      {/* ── 차트 카드 ── */}
      <div className={styles.chartCard}>
        <div className={styles.chartTitleRow}>
          <span className={styles.chartTitle}>총 평가금액 (USD)</span>
          {latest && (
            <span className={styles.chartLatest}>{fmtUSD(latest.totalValue)}</span>
          )}
        </div>

        {loading && <div className={styles.stateBox}><span className={styles.stateText}>로딩 중…</span></div>}

        {!loading && error && (
          <div className={styles.stateBox}>
            <span className={styles.stateText}>{error}</span>
            <button className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
          </div>
        )}

        {!loading && !error && points.length === 0 && (
          <div className={styles.stateBox}>
            <span className={styles.stateText}>아직 자산 기록이 없습니다.</span>
            <span className={styles.stateDesc}>
              Python 스케줄러가 매일 스냅샷을 저장합니다.
            </span>
          </div>
        )}

        {!loading && !error && points.length > 0 && (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart
              data={points}
              margin={{ top: 10, right: 16, left: 0, bottom: 4 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--border)"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tickFormatter={fmtAxisDate}
                tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                axisLine={false}
                tickLine={false}
                tickMargin={8}
              />
              <YAxis
                domain={yDomain}
                tickFormatter={(v) =>
                  v >= 1000
                    ? `$${(v / 1000).toFixed(0)}k`
                    : `$${v}`
                }
                tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }}
                axisLine={false}
                tickLine={false}
                width={56}
              />
              <Tooltip content={<CustomTooltip />} />
              {/* 매입원가 기준선 */}
              {summary?.totalCost != null && (
                <ReferenceLine
                  y={summary.totalCost}
                  stroke="var(--border2)"
                  strokeDasharray="4 4"
                  label={{
                    value: '매입원가',
                    position: 'insideTopRight',
                    fontSize: 10,
                    fill: 'var(--text-3)',
                    fontFamily: 'Inter',
                  }}
                />
              )}
              <Line
                type="monotone"
                dataKey="totalValue"
                stroke="var(--flee)"
                strokeWidth={2}
                dot={points.length === 1
                  ? { r: 5, fill: 'var(--flee)', strokeWidth: 0 }
                  : { r: 3, fill: 'var(--flee)', strokeWidth: 0 }
                }
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── 데이터 포인트 목록 ── */}
      {!loading && points.length > 0 && (
        <div className={styles.pointsCard}>
          <div className={styles.pointsHeader}>
            <div className={styles.pointsTh}>날짜</div>
            <div className={`${styles.pointsTh} ${styles.thRight}`}>평가금액</div>
            <div className={`${styles.pointsTh} ${styles.thRight}`}>총 수익률</div>
          </div>
          {[...points].reverse().map((p) => (
            <div key={p.date} className={styles.pointsRow}>
              <div className={styles.pointsDate}>
                {new Date(p.date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
              </div>
              <div className={`${styles.pointsValue} ${styles.thRight}`}>
                {fmtUSD(p.totalValue)}
              </div>
              <div className={`${styles.thRight}`} style={{ color: pctColor(p.totalReturnPct) }}>
                {fmtPct(p.totalReturnPct)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
