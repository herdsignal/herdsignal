import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fmtAxisDate } from './historyModel'
import styles from './History.module.css'

function PerformanceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipDate}>{label}</div>
      {payload.map((item) => (
        <div className={styles.tooltipRow} key={item.dataKey}>
          <span className={styles.tooltipLabel}>
            {item.dataKey === 'portfolioIndex' ? '내 계좌' : 'SPY'}
          </span>
          <span className={styles.tooltipValue}>{Number(item.value).toFixed(2)}</span>
        </div>
      ))}
    </div>
  )
}

export default function PerformanceChart({ points }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={points} margin={{ top: 10, right: 16, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="4 6" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={fmtAxisDate}
          tick={{ fontSize: 11, fill: 'var(--text-3)' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: 'var(--text-3)' }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip content={<PerformanceTooltip />} />
        <Line type="monotone" dataKey="portfolioIndex" stroke="var(--flee)" dot={false} strokeWidth={2.5} />
        <Line type="monotone" dataKey="benchmarkIndex" stroke="var(--text-3)" dot={false} strokeWidth={1.5} />
      </LineChart>
    </ResponsiveContainer>
  )
}
