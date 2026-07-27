import { useId } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { scoreColor, stageLabelFromScore } from '../../utils/herdStage'
import styles from './PriceHerdTimelineChart.module.css'

const formatDate = (value) => {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return `${String(date.getFullYear()).slice(2)}.${String(date.getMonth() + 1).padStart(2, '0')}`
}

const formatPrice = (value) => (
  Number.isFinite(Number(value))
    ? `$${Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })}`
    : '—'
)

function TimelineTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload
  if (!point) return null
  return (
    <div className={styles.tooltip}>
      <span>{point.marketSession ?? point.date}</span>
      <strong>{formatPrice(point.adjustedClose)}</strong>
      <em style={{ color: scoreColor(point.score) }}>
        HERD {Math.round(point.score)} · {point.stage ?? stageLabelFromScore(point.score)}
      </em>
    </div>
  )
}

export default function PriceHerdTimelineChart({
  points = [],
  currentScore = null,
}) {
  const gradientId = useId().replace(/:/g, '')
  const pricedCount = points.filter((point) => point.adjustedClose != null).length
  const score = currentScore ?? points.at(-1)?.score ?? null
  const color = scoreColor(score)

  if (!points.length) {
    return (
      <div className={styles.empty}>
        <strong>가격·HERD 이력 없음</strong>
        <span>주간 관찰값이 쌓이면 같은 시점의 수정 종가와 함께 표시됩니다.</span>
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.coverage}>
        수정 종가 연결 {pricedCount}/{points.length}
      </div>
      <ResponsiveContainer width="100%" height={178}>
        <LineChart
          data={points}
          syncId="stock-price-herd"
          margin={{ top: 12, right: 16, left: 4, bottom: 0 }}
        >
          <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.055)" />
          <XAxis dataKey="date" hide />
          <YAxis
            domain={['auto', 'auto']}
            tickFormatter={(value) => `$${Math.round(value)}`}
            tick={{ fontSize: 10, fill: 'var(--text-3)' }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<TimelineTooltip />} />
          <Line
            type="monotone"
            dataKey="adjustedClose"
            stroke="var(--text-1)"
            strokeWidth={1.8}
            dot={false}
            activeDot={{ r: 3, strokeWidth: 0 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className={styles.divider}>
        <span>수정 종가</span>
        <span>HERD</span>
      </div>
      <ResponsiveContainer width="100%" height={145}>
        <AreaChart
          data={points}
          syncId="stock-price-herd"
          margin={{ top: 2, right: 16, left: 4, bottom: 4 }}
        >
          <defs>
            <linearGradient id={`priceHerdFill-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.22} />
              <stop offset="100%" stopColor={color} stopOpacity={0.015} />
            </linearGradient>
          </defs>
          <ReferenceArea y1={0} y2={15} fill="#3B82F6" fillOpacity={0.065} />
          <ReferenceArea y1={15} y2={40} fill="#60A5FA" fillOpacity={0.04} />
          <ReferenceArea y1={60} y2={75} fill="#FB923C" fillOpacity={0.04} />
          <ReferenceArea y1={75} y2={100} fill="#EF4444" fillOpacity={0.065} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            interval="preserveStartEnd"
            minTickGap={42}
            tick={{ fontSize: 10, fill: 'var(--text-3)' }}
            axisLine={false}
            tickLine={false}
            tickMargin={8}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 40, 60, 100]}
            tick={{ fontSize: 10, fill: 'var(--text-3)' }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<TimelineTooltip />} />
          <Area
            type="monotone"
            dataKey="score"
            stroke={color}
            strokeWidth={1.8}
            fill={`url(#priceHerdFill-${gradientId})`}
            dot={points.length <= 12 ? { r: 2, fill: color, strokeWidth: 0 } : false}
            activeDot={{ r: 3.5, strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
      <div className={styles.legend}>
        <span>Flee</span><span>Scatter</span><span>Calm</span><span>Drift</span><span>Rush</span>
      </div>
    </div>
  )
}
