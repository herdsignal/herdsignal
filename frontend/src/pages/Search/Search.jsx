/**
 * Search.jsx — 종목 검색 페이지 (/search)
 *
 * 구성:
 *   1) 페이지 헤더
 *   2) 검색 바 (디바운스 300ms, 2글자 이상 → State S1 조회)
 *   3) 검색 결과 드롭다운 (HERD 점수 + 포트폴리오/관심종목 추가 버튼)
 *   4) 최근 검색 목록 (localStorage, 최대 5개)
 *
 * 래퍼런스: wireframes/wireframe-search.html
 */

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

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* 최근 검색 클릭 → 검색창에 자동 입력 */
  function handleRecentClick(ticker) {
    setQuery(ticker)
    inputRef.current?.focus()
  }

  /* 드롭다운 표시 여부 */
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

  /* ── JSX ── */
  return (
    <div>

      {/* 페이지 헤더 */}
      <div className={styles.pageHeader}>
        <div className={styles.pageDate}>{today}</div>
        <h1 className={styles.pageTitle}>종목 검색</h1>
        <p className={styles.pageDesc}>
          HERD 관찰 가능한 종목을 찾아 포트폴리오나 관찰 대기열에 추가하세요
        </p>
      </div>

      <section className={styles.searchPanel}>
        <div className={styles.searchPanelHead}>
          <div>
            <span>Inclusion Check</span>
            <strong>포트폴리오 편입 판단</strong>
          </div>
          <em>{portfolioTickers.size}개 보유 · {watchlistTickers.size}개 대기</em>
        </div>

        {/* 검색 바 */}
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
          <span className={styles.searchIcon}>⌕</span>
        </div>

        <div className={styles.searchGuide}>
          <div>
            <span>Ready</span>
            <strong>편입 가능</strong>
          </div>
          <div>
            <span>Pending</span>
            <strong>계산 대기</strong>
          </div>
          <div>
            <span>Limited</span>
            <strong>보류 우선</strong>
          </div>
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

      {/* 검색 결과 드롭다운 */}
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

      {/* 최근 검색 */}
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
    </div>
  )
}
