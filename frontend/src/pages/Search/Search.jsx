/**
 * Search.jsx — 종목 검색 페이지 (/search)
 *
 * 구성:
 *   1) 페이지 헤더
 *   2) 검색 바 (디바운스 300ms, 2글자 이상 → getStockHerd 조회)
 *   3) 검색 결과 드롭다운 (HERD 점수 + 포트폴리오/관심종목 추가 버튼)
 *   4) 인기 종목 3열 그리드 (마운트 시 6개 병렬 조회)
 *   5) 최근 검색 목록 (localStorage, 최대 5개)
 *
 * 래퍼런스: wireframes/wireframe-search.html
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate }                  from 'react-router-dom'
import { getStockHerd, addToPortfolio, addToWatchlist } from '../../api/herdApi'
import styles from './Search.module.css'

/* ── 상수 ─────────────────────────────── */

const POPULAR_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'META', 'TSLA', 'SPY']

/* 인기 종목 표시명 */
const TICKER_NAMES = {
  NVDA: 'NVIDIA Corporation',
  AAPL: 'Apple Inc.',
  MSFT: 'Microsoft Corporation',
  META: 'Meta Platforms',
  TSLA: 'Tesla, Inc.',
  SPY:  'S&P 500 ETF',
}

/* localStorage 키 */
const RECENT_KEY = 'hs_recent_searches'

/* ── 유틸 ─────────────────────────────── */

/** herdStage 정규화: "Herd Scatter" → "scatter" */
function normalizeStage(stage) {
  const s = (stage || '').toLowerCase()
  return s.startsWith('herd ') ? s.slice(5) : s
}

/** 단계 → CSS 변수 색상 */
function stageColor(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return 'var(--rush)'
    case 'drift':   return 'var(--drift)'
    case 'scatter': return 'var(--scatter)'
    case 'flee':    return 'var(--flee)'
    default:        return 'var(--calm)'
  }
}

/** stage → 배지 인라인 스타일 */
function badgeColors(stage) {
  switch (normalizeStage(stage)) {
    case 'rush':    return { background: 'rgba(239,68,68,0.12)',   color: 'var(--rush)' }
    case 'drift':   return { background: 'rgba(249,115,22,0.12)',  color: 'var(--drift)' }
    case 'scatter': return { background: 'rgba(96,165,250,0.12)',  color: 'var(--scatter)' }
    case 'flee':    return { background: 'rgba(59,130,246,0.12)',  color: 'var(--flee)' }
    default:        return { background: 'rgba(113,113,122,0.12)', color: 'var(--calm)' }
  }
}

/** stage 표시 문자열: "Herd Scatter" 형태 보장 */
function stageDisplay(stage) {
  if (!stage) return 'Herd Calm'
  return stage.startsWith('Herd ') ? stage : `Herd ${stage}`
}

/* 최근 검색 localStorage 조작 */
function loadRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
}
function saveToRecent(ticker) {
  const list = loadRecent().filter(t => t !== ticker)
  list.unshift(ticker)
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 5)))
}

/** 추가 버튼 레이블 */
function addBtnLabel(status, idleLabel) {
  if (status === 'loading') return '…'
  if (status === 'added')   return '추가됨 ✓'
  if (status === 'exists')  return '이미 추가됨'
  return idleLabel
}

/* ── 컴포넌트 ─────────────────────────── */

export default function Search() {
  const navigate = useNavigate()
  const inputRef = useRef(null)

  /* 검색 입력값 */
  const [query, setQuery] = useState('')

  /*
   * searchResult: null | { status: 'loading'|'found'|'not_found', data?: object }
   * - null: 검색 비활성 (query < 2글자)
   * - loading: API 호출 중
   * - found: 결과 있음 (data에 HERD 데이터)
   * - not_found: 결과 없음 또는 API 오류
   */
  const [searchResult, setSearchResult] = useState(null)

  /* 드롭다운 추가 버튼 상태 */
  const [portfolioStatus, setPortfolioStatus] = useState('idle')
  const [watchlistStatus, setWatchlistStatus] = useState('idle')

  /* 인기 종목 HERD 데이터 */
  const [popularData, setPopularData] = useState({})

  /* 최근 검색 (localStorage에서 초기값 로드) */
  const [recentSearches, setRecentSearches] = useState(loadRecent)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* ── 인기 종목 병렬 조회 (마운트 시 1회) ── */
  useEffect(() => {
    async function fetchPopular() {
      const results = await Promise.allSettled(
        POPULAR_TICKERS.map(t => getStockHerd(t))
      )
      const map = {}
      results.forEach((r, i) => {
        map[POPULAR_TICKERS[i]] = r.status === 'fulfilled'
          ? (r.value.data?.data ?? null)
          : null
      })
      setPopularData(map)
    }
    fetchPopular()
  }, [])

  /* ── 검색 디바운스 300ms ── */
  useEffect(() => {
    /* 2글자 미만이면 드롭다운 닫기 */
    if (query.length < 2) {
      setSearchResult(null)
      return
    }

    setSearchResult({ status: 'loading' })
    let cancelled = false

    const timer = setTimeout(async () => {
      const ticker = query.toUpperCase()
      try {
        const res  = await getStockHerd(ticker)
        if (cancelled) return   /* 언마운트 또는 query 변경으로 취소된 경우 무시 */
        const data = res.data?.data
        if (data) {
          setSearchResult({ status: 'found', data })
          /* 결과 있을 때만 최근 검색에 저장 */
          saveToRecent(ticker)
          setRecentSearches(loadRecent())
        } else {
          setSearchResult({ status: 'not_found' })
        }
      } catch {
        if (!cancelled) setSearchResult({ status: 'not_found' })
      }
    }, 300)

    /* 클린업: query 변경 시 이전 타이머 취소 + 진행 중 API 응답 무시 */
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query])

  /* 검색 결과가 바뀌면 추가 버튼 상태 초기화 */
  useEffect(() => {
    setPortfolioStatus('idle')
    setWatchlistStatus('idle')
  }, [searchResult?.data?.ticker])

  /* ── 추가 버튼 핸들러 ── */
  async function handleAddPortfolio(ticker) {
    if (portfolioStatus !== 'idle') return
    setPortfolioStatus('loading')
    try {
      await addToPortfolio(ticker)
      setPortfolioStatus('added')
    } catch (e) {
      setPortfolioStatus(e.response?.status === 409 ? 'exists' : 'idle')
    }
  }

  async function handleAddWatchlist(ticker) {
    if (watchlistStatus !== 'idle') return
    setWatchlistStatus('loading')
    try {
      await addToWatchlist(ticker)
      setWatchlistStatus('added')
    } catch (e) {
      setWatchlistStatus(e.response?.status === 409 ? 'exists' : 'idle')
    }
  }

  /* 최근 검색 클릭 → 검색창에 자동 입력 */
  function handleRecentClick(ticker) {
    setQuery(ticker)
    inputRef.current?.focus()
  }

  /* 드롭다운 표시 여부 */
  const showDropdown = query.length >= 2 && searchResult !== null

  /* ── 드롭다운 콘텐츠 렌더 헬퍼 ── */
  function renderDropdownContent() {
    if (searchResult.status === 'loading') {
      return <div className={styles.dropdownPlaceholder}>검색 중…</div>
    }

    if (searchResult.status === 'not_found') {
      return (
        <div className={styles.dropdownPlaceholder}>
          데이터가 없습니다. 스케줄러 실행 후 조회 가능합니다.
        </div>
      )
    }

    /* status === 'found' */
    const d     = searchResult.data
    const color = stageColor(d.herdStage)
    const badge = badgeColors(d.herdStage)
    const label = d.ticker.length <= 4 ? d.ticker : d.ticker.slice(0, 4)

    return (
      <div
        className={styles.searchResultItem}
        onClick={() => navigate(`/stock/${d.ticker}`)}
      >
        {/* 좌: 배지 + 티커/종목명 */}
        <div className={styles.resultLeft}>
          <div className={styles.resultBadge} style={badge}>{label}</div>
          <div>
            <div className={styles.resultTicker}>{d.ticker}</div>
            <div className={styles.resultName}>
              {TICKER_NAMES[d.ticker] ?? '미국 주식'}
            </div>
          </div>
        </div>

        {/* 우: HERD 점수 + 추가 버튼 (이벤트 버블링 차단하여 상세 이동 방지) */}
        <div className={styles.resultRight} onClick={e => e.stopPropagation()}>
          <div className={styles.resultHerd}>
            <div className={styles.resultHerdScore} style={{ color }}>
              {Math.round(d.herdScore)}
            </div>
            <div className={styles.resultHerdStage}>
              {stageDisplay(d.herdStage)}
            </div>
          </div>

          {/* + 포트폴리오 */}
          <button
            className={`${styles.resultAddBtn} ${
              portfolioStatus === 'added' || portfolioStatus === 'exists'
                ? styles.resultAddBtnDone : ''
            }`}
            onClick={() => handleAddPortfolio(d.ticker)}
            disabled={portfolioStatus === 'loading'}
          >
            {addBtnLabel(portfolioStatus, '+ 포트폴리오')}
          </button>

          {/* + 관심종목 */}
          <button
            className={`${styles.resultAddBtn} ${
              watchlistStatus === 'added' || watchlistStatus === 'exists'
                ? styles.resultAddBtnDone : ''
            }`}
            onClick={() => handleAddWatchlist(d.ticker)}
            disabled={watchlistStatus === 'loading'}
          >
            {addBtnLabel(watchlistStatus, '+ 관심종목')}
          </button>
        </div>
      </div>
    )
  }

  /* ── JSX ── */
  return (
    <div>

      {/* 페이지 헤더 */}
      <div className={styles.pageHeader}>
        <div className={styles.pageDate}>{today}</div>
        <h1 className={styles.pageTitle}>종목 검색</h1>
        <p className={styles.pageDesc}>
          티커 또는 종목명으로 검색해 포트폴리오에 추가하세요
        </p>
      </div>

      {/* 검색 바 */}
      <div className={styles.searchWrap}>
        <input
          ref={inputRef}
          className={styles.searchInput}
          type="text"
          placeholder="티커 또는 종목명 입력 (예: AAPL, Tesla)"
          value={query}
          onChange={e => setQuery(e.target.value.toUpperCase())}
          autoComplete="off"
          spellCheck={false}
        />
        <span className={styles.searchIcon}>⌕</span>
      </div>

      {/* 검색 결과 드롭다운 */}
      {showDropdown && (
        <div className={styles.searchDropdown}>
          <div className={styles.dropdownHeader}>검색 결과</div>
          {renderDropdownContent()}
        </div>
      )}

      {/* 인기 종목 HERD */}
      <div className={styles.sectionLabel}>인기 종목 HERD</div>
      <div className={styles.popularGrid}>
        {POPULAR_TICKERS.map(ticker => {
          const data  = popularData[ticker]
          const score = data?.herdScore ?? null
          const stage = data?.herdStage ?? null
          const color = stage ? stageColor(stage) : 'var(--text-3)'
          const badge = stage
            ? badgeColors(stage)
            : { background: 'var(--surface2)', color: 'var(--text-3)' }

          return (
            <div
              key={ticker}
              className={styles.popularCard}
              onClick={() => navigate(`/stock/${ticker}`)}
            >
              {/* 왼쪽 컬러 스트라이프 — ::before 대신 절대 위치 div 사용 */}
              <div className={styles.popularStripe} style={{ background: color }} />

              <div className={styles.popularTop}>
                <div className={styles.popularBadge} style={badge}>
                  {ticker.length <= 4 ? ticker : ticker.slice(0, 4)}
                </div>
                <div className={styles.popularScore} style={{ color }}>
                  {score !== null ? Math.round(score) : '—'}
                </div>
              </div>

              <div className={styles.popularTicker}>{ticker}</div>
              <div className={styles.popularName}>
                {TICKER_NAMES[ticker] ?? ticker}
              </div>
            </div>
          )
        })}
      </div>

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
    </div>
  )
}
