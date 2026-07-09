function sumBy(items, key) {
  return items.reduce((sum, item) => {
    const n = Number(item[key])
    return Number.isFinite(n) ? sum + n : sum
  }, 0)
}

function average(values) {
  const nums = values.map(Number).filter(Number.isFinite)
  if (nums.length === 0) return null
  return nums.reduce((sum, value) => sum + value, 0) / nums.length
}

export function summarizeSignalJournal(items) {
  const logs = Array.isArray(items) ? items : []
  const buys = logs.filter((item) => item.actionType === 'BUY')
  const sells = logs.filter((item) => item.actionType === 'SELL')
  const holds = logs.filter((item) => item.actionType === 'HOLD')
  const profitValues = sells.map((item) => item.profitPct)
  const outcomeValues = logs.map((item) => item.outcomePct)
  const avgProfitPct = average(profitValues)
  const avgOutcomePct = average(outcomeValues)

  return {
    totalCount: logs.length,
    buyCount: buys.length,
    sellCount: sells.length,
    holdCount: holds.length,
    buyAmount: sumBy(buys, 'amount'),
    sellAmount: sumBy(sells, 'amount'),
    avgProfitPct,
    avgOutcomePct,
    hasProfitData: avgProfitPct != null,
    hasOutcomeData: avgOutcomePct != null,
  }
}

export function formatJournalTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ko-KR', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatJournalPrice(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

export function formatJournalQuantity(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 4 })}주`
}

export function formatJournalAmount(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

export function formatJournalProfit(value) {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

export function formatJournalOutcome(value) {
  return formatJournalProfit(value)
}

export function formatJournalCount(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0회'
  return `${n.toLocaleString('ko-KR')}회`
}

export function formatJournalDuration(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return null
  return `신호 ${Math.round(n).toLocaleString('ko-KR')}일째`
}

export function formatOutcomeDays(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return null
  if (n === 0) return '오늘 기록'
  return `${Math.round(n).toLocaleString('ko-KR')}일 추적`
}
