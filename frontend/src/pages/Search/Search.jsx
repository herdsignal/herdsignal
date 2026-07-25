import { useState, useMemo, useRef } from 'react'
import { useNavigate }                  from 'react-router-dom'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import { useAuth } from '../../auth/AuthContext'
import { clearPortfolioCaches } from '../../features/portfolio/portfolioCache'
import SearchResultContent from './SearchResultContent'
import {
  STOCK_CANDIDATES,
  TICKER_NAMES,
  candidateMatches,
} from './searchModel'
import { useStockSearch } from './useStockSearch'
import { useTickerMembership } from './useTickerMembership'
import styles from './Search.module.css'

/* ── 컴포넌트 ─────────────────────────── */

export default function Search() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const inputRef = useRef(null)

  /* 검색 입력값 */
  const [query, setQuery] = useState('')

  const [modalTicker, setModalTicker] = useState(null)
  const { searchResult, recentSearches } = useStockSearch(query)
  const selectedTicker = searchResult?.data?.ticker ?? searchResult?.candidate?.ticker
  const {
    portfolioTickers,
    watchlistTickers,
    portfolioStatus,
    watchlistStatus,
    addError,
    handleAddPortfolio,
    handleAddWatchlist,
  } = useTickerMembership({
    selectedTicker,
    userId: user?.id,
    onPortfolioAdded: setModalTicker,
  })

  function handleRecentClick(ticker) {
    setQuery(ticker)
    inputRef.current?.focus()
  }

  const showDropdown = query.trim().length >= 2 && searchResult !== null

  const suggestionMatches = useMemo(() => {
    const normalized = query.trim().toUpperCase()
    if (normalized.length < 2) return []
    const resultMatches = searchResult?.matches
    if (Array.isArray(resultMatches) && resultMatches.length > 0) {
      return resultMatches.slice(0, 5)
    }
    return STOCK_CANDIDATES.filter((item) => candidateMatches(item, normalized)).slice(0, 5)
  }, [query, searchResult?.matches])

  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <span>STOCK FINDER</span>
        <h1>종목 찾기</h1>
        <p>티커나 기업명으로 State S1 관찰값을 찾습니다.</p>
      </header>

      <section className={styles.searchPanel}>
        <div className={styles.searchPanelHead}>
          <strong>미국 종목 검색</strong>
          <span>{portfolioTickers.size} 보유 · {watchlistTickers.size} 관심</span>
        </div>

        <div className={styles.searchWrap}>
          <input
            ref={inputRef}
            className={styles.searchInput}
            type="text"
            placeholder="티커 또는 종목명 입력 (예: AAPL, TSLA)"
            value={query}
            onChange={e => setQuery(e.target.value.toUpperCase())}
            autoComplete="off"
            spellCheck={false}
          />
          <span className={styles.searchIcon} aria-hidden="true">⌕</span>
        </div>
      </section>

      {suggestionMatches.length > 0 && (
        <div className={styles.suggestionRow}>
          {suggestionMatches.map((item) => (
            <button
              key={item.ticker}
              className={styles.suggestionChip}
              onClick={() => setQuery(item.ticker)}
            >
              <span>{item.ticker}</span>
              <small>{item.name}</small>
            </button>
          ))}
        </div>
      )}

      {showDropdown && (
        <div className={styles.searchDropdown}>
          <div className={styles.dropdownHeader}>검색 결과</div>
          <SearchResultContent
            result={searchResult}
            portfolioStatus={portfolioStatus}
            watchlistStatus={watchlistStatus}
            addError={addError}
            onAddPortfolio={handleAddPortfolio}
            onAddWatchlist={handleAddWatchlist}
            onOpen={(ticker) => navigate(`/stock/${ticker}`)}
          />
        </div>
      )}

      {recentSearches.length > 0 && (
        <>
          <div className={styles.sectionLabel}>최근 검색</div>
          <div className={styles.recentList}>
            {recentSearches.map(ticker => (
              <div
                key={ticker}
                className={styles.recentItem}
                onClick={() => handleRecentClick(ticker)}
              >
                <div className={styles.recentLeft}>
                  <span className={styles.recentIcon}>↺</span>
                  <div>
                    <div className={styles.recentTicker}>{ticker}</div>
                    <div className={styles.recentName}>
                      {TICKER_NAMES[ticker] ?? '미국 주식'}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {modalTicker && (
        <AvgPriceModal
          ticker={modalTicker}
          currentAvgPrice={null}
          currentQuantity={null}
          onClose={() => setModalTicker(null)}
          onSaved={() => {
            clearPortfolioCaches(user?.id)
            setModalTicker(null)
          }}
        />
      )}
    </main>
  )
}
