/**
 * HerdHistoryChart.jsx — HERD Index 히스토리 공용 차트.
 * 가격이 아니라 HERD 점수 흐름과 Flee~Rush 구간을 보여준다.
 */

import {
  Area,
  AreaChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useId } from 'react'
import styles from './HerdHistoryChart.module.css'

function scoreColor(score) {
  if (score == null) return 'var(--text-1)'
  if (score < 20) return 'var(--flee)'
  if (score < 40) return 'var(--scatter)'
  if (score < 60) return 'var(--calm)'
  if (score < 80) return 'var(--drift)'
  return 'var(--rush)'
}

function scoreStage(score) {
  if (score == null) return '—'
  if (score < 20) return 'Flee'
  if (score < 40) return 'Scatter'
  if (score < 60) return 'Calm'
  if (score < 80) return 'Drift'
  return 'Rush'
}

function formatAxisDate(dateStr, compact) {
  const d = new Date(`${dateStr}T00:00:00`)
  if (Number.isNaN(d.getTime())) return dateStr
  if (compact) return `${d.getMonth() + 1}/${d.getDate()}`
  return `${String(d.getFullYear()).slice(2)}.${String(d.getMonth() + 1).padStart(2, '0')}`
}

function formatScore(value) {
  if (value == null || Number.isNaN(value)) return '—'
  return Math.round(value)
}

function formatDelta(value) {
  if (value == null || Number.isNaN(value)) return '—'
  const rounded = Math.round(value)
  if (rounded > 0) return `+${rounded}`
  return `${rounded}`
}

function buildHistorySummary(points, current) {
  const scores = points
    .map((point) => Number(point.score))
    .filter((score) => Number.isFinite(score))

  if (!scores.length || current == null) return null

  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const average = scores.reduce((sum, score) => sum + score, 0) / scores.length
  const first = scores[0]
  const currentNumber = Number(current)
  const percentile = scores.length > 1
    ? (scores.filter((score) => score <= currentNumber).length / scores.length) * 100
    : null

  return {
    percentile,
    delta: currentNumber - first,
    average,
    range: `${formatScore(min)}-${formatScore(max)}`,
  }
}

function TooltipContent({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const score = payload[0]?.value
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipDate}>
        {label
          ? new Date(`${label}T00:00:00`).toLocaleDateString('ko-KR', {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })
          : ''}
      </div>
      <div className={styles.tooltipScore} style={{ color: scoreColor(score) }}>
        HERD {score != null ? Math.round(score) : '—'}
      </div>
      <div className={styles.tooltipStage}>{scoreStage(score)}</div>
    </div>
  )
}

export default function HerdHistoryChart({
  points = [],
  currentScore = null,
  height = 220,
  compact = false,
}) {
  const gradientId = useId().replace(/:/g, '')
  const hasHistory = points.length > 0
  const hasSparseHistory = points.length > 0 && points.length < 4
  const current = currentScore ?? points[points.length - 1]?.score ?? null
  const stroke = scoreColor(current)
  const summary = buildHistorySummary(points, current)

  if (!hasHistory) {
    return (
      <div className={styles.empty} style={{ height }}>
        <strong>HERD 이력 없음</strong>
        <span>계산된 HERD 스냅샷이 쌓이면 차트가 표시됩니다.</span>
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      {hasSparseHistory && (
        <div className={styles.sparseBadge}>
          이력 {points.length}개 · 백필 후 장기 히스토리 표시
        </div>
      )}
      {!compact && summary && (
        <div className={styles.summary}>
          <div className={styles.summaryItem}>
            <span>현재 위치</span>
            <strong>{summary.percentile == null ? '—' : `${Math.round(summary.percentile)}%`}</strong>
          </div>
          <div className={styles.summaryItem}>
            <span>기간 변화</span>
            <strong className={summary.delta > 0 ? styles.deltaUp : summary.delta < 0 ? styles.deltaDown : ''}>
              {formatDelta(summary.delta)}
            </strong>
          </div>
          <div className={styles.summaryItem}>
            <span>평균</span>
            <strong>{formatScore(summary.average)}</strong>
          </div>
          <div className={styles.summaryItem}>
            <span>범위</span>
            <strong>{summary.range}</strong>
          </div>
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={points} margin={{ top: 10, right: compact ? 6 : 16, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id={`herdHistoryFill-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.26} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <ReferenceArea y1={0} y2={20} fill="#3B82F6" fillOpacity={0.075} />
          <ReferenceArea y1={20} y2={40} fill="#60A5FA" fillOpacity={0.055} />
          <ReferenceArea y1={40} y2={60} fill="#A3AAB8" fillOpacity={0.04} />
          <ReferenceArea y1={60} y2={80} fill="#FB923C" fillOpacity={0.055} />
          <ReferenceArea y1={80} y2={100} fill="#EF4444" fillOpacity={0.075} />
          {[20, 40, 60, 80].map((line) => (
            <ReferenceLine
              key={line}
              y={line}
              stroke="rgba(255,255,255,0.08)"
              strokeDasharray="3 5"
            />
          ))}
          {current != null && (
            <ReferenceLine
              y={current}
              stroke={stroke}
              strokeOpacity={0.35}
              strokeDasharray="4 4"
            />
          )}
          <XAxis
            dataKey="date"
            tickFormatter={(v) => formatAxisDate(v, compact)}
            interval="preserveStartEnd"
            minTickGap={compact ? 28 : 38}
            tick={{ fontSize: 10, fill: 'var(--text-3)', fontFamily: 'Inter' }}
            axisLine={false}
            tickLine={false}
            tickMargin={8}
          />
          <YAxis
            domain={[0, 100]}
            ticks={compact ? [0, 50, 100] : [0, 20, 40, 60, 80, 100]}
            tick={{ fontSize: 10, fill: 'var(--text-3)', fontFamily: 'Inter' }}
            axisLine={false}
            tickLine={false}
            width={compact ? 24 : 30}
          />
          <Tooltip content={<TooltipContent />} />
          <Area
            type="monotone"
            dataKey="score"
            stroke={stroke}
            strokeWidth={compact ? 1.8 : 2}
            fill={`url(#herdHistoryFill-${gradientId})`}
            dot={points.length <= 12 ? { r: 2.2, fill: stroke, strokeWidth: 0 } : false}
            activeDot={{ r: 4, fill: stroke, strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
      {!compact && (
        <div className={styles.legend}>
          <span>Flee</span>
          <span>Scatter</span>
          <span>Calm</span>
          <span>Drift</span>
          <span>Rush</span>
        </div>
      )}
    </div>
  )
}
