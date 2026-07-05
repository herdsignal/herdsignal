import { useEffect, useState } from 'react'
import styles from './StockAvatar.module.css'

const ETF_TICKERS = new Set([
  'SPY', 'QQQ', 'DIA', 'IWM', 'VOO', 'VTI', 'VT',
  'SOXL', 'SOXS', 'TQQQ', 'SQQQ', 'BITX', 'IBIT', 'BITO',
  'XLK', 'XLF', 'XLE', 'XLV', 'XLY', 'XLP', 'XLU', 'XLI',
])

function tickerLabel(ticker) {
  const normalized = (ticker || '').toUpperCase()
  return normalized.length <= 4 ? normalized : normalized.slice(0, 4)
}

function isEtfTicker(ticker) {
  return ETF_TICKERS.has((ticker || '').toUpperCase())
}

export default function StockAvatar({
  ticker,
  logoUrl,
  size = 'md',
  tone,
  className = '',
}) {
  const [failed, setFailed] = useState(false)
  const hasLogo = Boolean(logoUrl) && !failed
  const isEtfFallback = !hasLogo && isEtfTicker(ticker)

  useEffect(() => {
    setFailed(false)
  }, [logoUrl])

  return (
    <div
      className={`${styles.avatar} ${styles[size] ?? styles.md} ${hasLogo ? styles.hasLogo : ''} ${isEtfFallback ? styles.etfFallback : ''} ${className}`}
      style={{
        '--avatar-bg': tone?.bg,
        '--avatar-color': tone?.color,
      }}
    >
      {hasLogo ? (
        <img
          src={logoUrl}
          alt={`${ticker} logo`}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <span>{tickerLabel(ticker)}</span>
      )}
    </div>
  )
}
