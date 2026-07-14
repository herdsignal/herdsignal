import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { ASSET_HISTORY_PERIODS, fmtAxisDate, fmtPct, pctColor } from './dashboardModel'
import styles from './Dashboard.module.css'

export default function DashboardAssetHistory({
  summary, cashBalance, history, latest, first, startValue,
  totalFlowPct, investedChangePct, drawdownPct, yDomain,
  period, periodLabel, startLabel, loading, error,
  displayAmount, onPeriodChange,
}) {
  return (
    <div className={styles.assetPanel}>
      <div className={styles.assetPanelHeader}>
        <div>
          <div className={styles.assetPanelLabel}>Asset History · {periodLabel}</div>
          <div className={styles.assetPanelTitle}>{latest ? displayAmount(latest.totalAssetValue) : displayAmount(summary.total_value)}</div>
          <div className={styles.assetPanelSub}>총자산은 입출금 포함 · 투자 변화는 주식 평가액 기준 · 기간 시작 {startLabel}{first?.totalAssetValue != null ? ` · ${displayAmount(first.totalAssetValue)}` : ''}</div>
        </div>
        <div className={styles.assetPeriodToggle}>
          {ASSET_HISTORY_PERIODS.map((item) => <button key={item.value} type="button" className={`${styles.assetPeriodBtn} ${period === item.value ? styles.assetPeriodBtnActive : ''}`} onClick={() => onPeriodChange(item.value)}>{item.label}</button>)}
        </div>
      </div>
      <div className={styles.assetStats}>
        <AssetStat label="주식 평가액 변화" value={fmtPct(investedChangePct)} detail="현금 변동 제외" tone={pctColor(investedChangePct)} />
        <AssetStat label="총자산 변화" value={fmtPct(totalFlowPct)} detail="입출금 포함" tone={pctColor(totalFlowPct)} />
        <AssetStat label="고점 대비" value={fmtPct(drawdownPct)} detail="현재 총자산 기준" tone={pctColor(drawdownPct)} />
        <AssetStat label="현재 현금" value={displayAmount(summary.cash_balance ?? cashBalance)} detail="총자산에 포함" />
      </div>
      {loading && <div className={styles.assetState}>히스토리 로딩 중…</div>}
      {!loading && error && <div className={styles.assetState}>{error}</div>}
      {!loading && !error && history.length === 0 && <div className={styles.assetState}>아직 자산 히스토리가 없습니다.</div>}
      {!loading && !error && history.length > 0 && (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={history} margin={{ top: 12, right: 14, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="4 6" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={fmtAxisDate} tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }} axisLine={false} tickLine={false} tickMargin={8} />
            <YAxis domain={yDomain} tickFormatter={(value) => value >= 1000 ? `$${(value / 1000).toFixed(0)}k` : `$${value}`} tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'Inter' }} axisLine={false} tickLine={false} width={56} />
            <Tooltip content={<AssetTooltip displayAmount={displayAmount} />} />
            {summary.total_cost != null && <ReferenceLine y={summary.total_cost} stroke="rgba(163, 170, 184, 0.55)" strokeDasharray="4 4" />}
            {startValue != null && <ReferenceLine y={startValue} stroke="rgba(59, 130, 246, 0.45)" strokeDasharray="5 5" />}
            <Line type="monotone" dataKey="totalAssetValue" stroke="var(--flee)" strokeWidth={2.5} dot={history.length === 1 ? { r: 5, fill: 'var(--flee)', strokeWidth: 0 } : false} activeDot={{ r: 5, strokeWidth: 0 }} />
            <Line type="monotone" dataKey="investedValue" stroke="var(--calm)" strokeWidth={1.8} strokeDasharray="5 5" dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

function AssetStat({ label, value, detail, tone }) {
  return <div><span>{label}</span><strong style={tone ? { color: tone } : undefined}>{value}</strong><em>{detail}</em></div>
}

function AssetTooltip({ active, payload, label, displayAmount }) {
  if (!active || !payload?.length) return null
  const date = new Date(label)
  const dateText = Number.isNaN(date.getTime()) ? label : date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
  const row = payload[0]?.payload
  return <div className={styles.assetTooltip}><div className={styles.assetTooltipDate}>{dateText}</div>{[['총자산', row?.totalAssetValue], ['주식 평가액', row?.investedValue], ['현금', row?.cashBalance]].map(([name, value]) => <div key={name} className={styles.assetTooltipRow}><span>{name}</span><strong>{displayAmount(value)}</strong></div>)}</div>
}
