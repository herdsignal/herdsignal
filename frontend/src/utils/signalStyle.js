const SIGNAL_STYLES = {
  BUY: { bg: 'var(--action-buy-soft)', color: 'var(--action-buy)' },
  ADD: { bg: 'var(--action-add-soft)', color: 'var(--action-add)' },
  HOLD: { bg: 'var(--action-hold-soft)', color: 'var(--action-hold)' },
  REDUCE: { bg: 'var(--action-reduce-soft)', color: 'var(--action-reduce)' },
  SELL: { bg: 'var(--action-sell-soft)', color: 'var(--action-sell)' },
}

export function signalStyle(signal) {
  return SIGNAL_STYLES[signal] ?? SIGNAL_STYLES.HOLD
}

export function signalTone(signal) {
  if (signal === 'BUY' || signal === 'ADD') return 'buy'
  if (signal === 'SELL' || signal === 'REDUCE') return 'reduce'
  return 'hold'
}
