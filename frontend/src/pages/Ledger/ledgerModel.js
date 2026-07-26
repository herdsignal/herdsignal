export const ENTRY_TYPES = {
  BUY: '매수',
  SELL: '매도',
  DEPOSIT: '입금',
  WITHDRAWAL: '출금',
  DIVIDEND: '배당',
  FEE: '비용',
  SPLIT: '주식 분할',
}

export const isTrade = (type) => type === 'BUY' || type === 'SELL'
export const needsTicker = (type) =>
  isTrade(type) || type === 'DIVIDEND' || type === 'SPLIT'

export function entryPayload(form) {
  const payload = {
    entryType: form.entryType,
    occurredOn: form.occurredOn,
    note: form.note.trim() || null,
  }
  if (needsTicker(form.entryType)) payload.ticker = form.ticker.trim().toUpperCase()
  if (isTrade(form.entryType)) {
    payload.quantity = Number(form.quantity)
    payload.unitPrice = Number(form.unitPrice)
    payload.fee = Number(form.fee || 0)
  } else if (form.entryType === 'SPLIT') {
    payload.splitRatio = Number(form.splitRatio)
  } else {
    payload.amount = Number(form.amount)
  }
  return payload
}

export function formatUsd(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(Number(value))
}

export function formatSignedUsd(value) {
  if (value == null) return '—'
  const number = Number(value)
  return `${number > 0 ? '+' : ''}${formatUsd(number)}`
}
