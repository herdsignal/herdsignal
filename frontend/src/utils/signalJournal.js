export const SIGNAL_JOURNAL_KEY = 'hs_signal_journal'
const MAX_JOURNAL_ITEMS = 200

function readAll() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SIGNAL_JOURNAL_KEY) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeAll(items) {
  try {
    localStorage.setItem(SIGNAL_JOURNAL_KEY, JSON.stringify(items.slice(0, MAX_JOURNAL_ITEMS)))
  } catch {
    /* localStorage 실패 무시 */
  }
}

export function readSignalJournal(ticker) {
  const items = readAll()
  if (!ticker) return items
  const normalized = ticker.toUpperCase()
  return items.filter((item) => item.ticker === normalized)
}

export function appendSignalJournal(entry) {
  const ticker = entry.ticker?.toUpperCase()
  const next = [
    {
      id: `${Date.now()}-${ticker}`,
      createdAt: new Date().toISOString(),
      ...entry,
      ticker,
    },
    ...readAll(),
  ]
  writeAll(next)
  return next.filter((item) => item.ticker === ticker).slice(0, 5)
}

export function removeSignalJournal(id, ticker) {
  const next = readAll().filter((item) => item.id !== id)
  writeAll(next)
  return readSignalJournal(ticker).filter((item) => item.id !== id).slice(0, 5)
}

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
  const avgProfitPct = average(profitValues)

  return {
    totalCount: logs.length,
    buyCount: buys.length,
    sellCount: sells.length,
    holdCount: holds.length,
    buyAmount: sumBy(buys, 'amount'),
    sellAmount: sumBy(sells, 'amount'),
    avgProfitPct,
    hasProfitData: avgProfitPct != null,
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

export function formatJournalCount(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0회'
  return `${n.toLocaleString('ko-KR')}회`
}
