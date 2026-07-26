import { forwardRef } from 'react'
import styles from './TickerSearch.module.css'

const TickerSearch = forwardRef(function TickerSearch({
  query,
  suggestions = [],
  onQueryChange,
  onSuggestionSelect,
  onSubmit,
  recentTickers = [],
  onRecentSelect,
  label = '티커 또는 종목명 검색',
  placeholder = '티커 또는 기업명',
  size = 'default',
}, ref) {
  return (
    <div className={`${styles.search} ${size === 'large' ? styles.large : ''}`}>
      <form
        className={styles.inputWrap}
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit?.()
        }}
      >
        <span className={styles.dotMark} aria-hidden="true">
          {Array.from({ length: 9 }, (_, index) => <i key={index} />)}
        </span>
        <input
          ref={ref}
          type="search"
          aria-label={label}
          placeholder={placeholder}
          value={query}
          onChange={(event) => onQueryChange(event.target.value.toUpperCase())}
          autoComplete="off"
          spellCheck={false}
        />
        <kbd aria-hidden="true">Enter</kbd>
      </form>

      {suggestions.length > 0 && (
        <div className={styles.suggestions} aria-label="검색 제안">
          {suggestions.map((item) => (
            <button
              type="button"
              key={item.ticker}
              onClick={() => onSuggestionSelect(item)}
            >
              <strong>{item.ticker}</strong>
              <span>{item.name}</span>
            </button>
          ))}
        </div>
      )}

      {recentTickers.length > 0 && (
        <div className={styles.recent} aria-label="최근 검색">
          <span>최근</span>
          {recentTickers.slice(0, 3).map((ticker) => (
            <button
              type="button"
              key={ticker}
              onClick={() => onRecentSelect?.(ticker)}
            >
              {ticker}
            </button>
          ))}
        </div>
      )}
    </div>
  )
})

export default TickerSearch
