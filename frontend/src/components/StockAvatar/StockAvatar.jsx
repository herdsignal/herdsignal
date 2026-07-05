import { useEffect, useState } from 'react'
import styles from './StockAvatar.module.css'

function tickerLabel(ticker) {
  const normalized = (ticker || '').toUpperCase()
  return normalized.length <= 4 ? normalized : normalized.slice(0, 4)
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

  useEffect(() => {
    setFailed(false)
  }, [logoUrl])

  return (
    <div
      className={`${styles.avatar} ${styles[size] ?? styles.md} ${hasLogo ? styles.hasLogo : ''} ${className}`}
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
