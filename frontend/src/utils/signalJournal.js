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
  const next = [
    {
      id: `${Date.now()}-${entry.ticker}`,
      createdAt: new Date().toISOString(),
      ...entry,
    },
    ...readAll(),
  ]
  writeAll(next)
  return next.filter((item) => item.ticker === entry.ticker).slice(0, 5)
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
