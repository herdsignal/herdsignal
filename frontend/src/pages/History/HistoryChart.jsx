import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fmtAxisDate, fmtPct, fmtUSD, pctColor } from './historyModel'
import styles from './History.module.css'

function HistoryTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const date = new Date(label)
  const dateLabel = Number.isNaN(date.getTime())
    ? label
    : date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
  const totalValue = payload.find((item) => item.dataKey === 'totalValue')?.value
  const totalReturnPct = payload.find((item) => item.dataKey === 'totalReturnPct')?.value

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipDate}>{dateLabel}</div>
      <div className={styles.tooltipRow}>
        <span className={styles.tooltipLabel}>평가금액</span>
        <span className={styles.tooltipValue}>{fmtUSD(totalValue)}</span>
      </div>
      {totalReturnPct != null && (
        <div className={styles.tooltipRow}>
          <span className={styles.tooltipLabel}>총 수익률</span>
          <span style={{ color: pctColor(totalReturnPct) }}>{fmtPct(totalReturnPct)}</span>
        </div>
      )}
    </div>
  )
}

export default function HistoryChart({ points, totalCost, yDomain }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={points} margin={{ top: 10, right: 16, left: 0, bottom: 4 }}>
        <CartesianGrid
          strokeDasharray="4 6"
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
          tickFormatter={(value) => value >= 1000 ? `$${(value / 1000).toFixed(0)}k` : `$${value}`}
          tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }}
          axisLine={false}
          tickLine={false}
          width={56}
        />
        <Tooltip content={<HistoryTooltip />} />
        {totalCost != null && (
          <ReferenceLine
            y={totalCost}
            stroke="rgba(163, 170, 184, 0.5)"
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
          strokeWidth={2.5}
          dot={points.length === 1
            ? { r: 5, fill: 'var(--flee)', strokeWidth: 0 }
            : { r: 3, fill: 'var(--flee)', strokeWidth: 0 }}
          activeDot={{ r: 5, strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
