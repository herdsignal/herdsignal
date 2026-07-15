/**
 * Search.jsx — 종목 검색 페이지 (/search)
 *
 * 구성:
 *   1) 페이지 헤더
 *   2) 검색 바 (디바운스 300ms, 2글자 이상 → getStockHerd 조회)
 *   3) 검색 결과 드롭다운 (HERD 점수 + 포트폴리오/관심종목 추가 버튼)
 *   4) 최근 검색 목록 (localStorage, 최대 5개)
 *
 * 래퍼런스: wireframes/wireframe-search.html
 */

import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate }                  from 'react-router-dom'
import {
  getPortfolio,
  getWatchlist,
  getStockHerd,
  searchStocks,
  addToPortfolio,
  addToWatchlist,
} from '../../api/herdApi'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import StockAvatar from '../../components/StockAvatar/StockAvatar'
import { qualityReasonText, shouldShowQuality } from '../../utils/dataQuality'
import { useAuth } from '../../auth/AuthContext'
import { clearPortfolioCaches } from '../Dashboard/dashboardModel'
import styles from './Search.module.css'

/* ── 상수 ─────────────────────────────── */

const STOCK_CANDIDATES = [
  { ticker: 'NVDA', name: 'NVIDIA Corporation', sector: 'Semiconductors' },
  { ticker: 'AAPL', name: 'Apple Inc.', sector: 'Consumer Technology' },
  { ticker: 'MSFT', name: 'Microsoft Corporation', sector: 'Software' },
  { ticker: 'META', name: 'Meta Platforms', sector: 'Communication Services' },
  { ticker: 'TSLA', name: 'Tesla, Inc.', sector: 'EV / Auto' },
  { ticker: 'GOOGL', name: 'Alphabet Inc.', sector: 'Communication Services' },
  { ticker: 'AMZN', name: 'Amazon.com, Inc.', sector: 'Consumer Discretionary' },
  { ticker: 'PLTR', name: 'Palantir Technologies', sector: 'Software' },
  { ticker: 'IONQ', name: 'IonQ, Inc.', sector: 'Quantum Computing' },
  { ticker: 'SNDK', name: 'Sandisk Corporation', sector: 'Semiconductors / Storage' },
  { ticker: 'BITX', name: '2x Bitcoin Strategy ETF', sector: 'Crypto ETF' },
  { ticker: 'SPY', name: 'S&P 500 ETF', sector: 'Benchmark ETF' },
  { ticker: 'QQQ', name: 'Nasdaq 100 ETF', sector: 'Benchmark ETF' },
]

const TICKER_META = Object.fromEntries(STOCK_CANDIDATES.map(item => [item.ticker, item]))
const TICKER_NAMES = Object.fromEntries(STOCK_CANDIDATES.map(item => [item.ticker, item.name]))

/* localStorage 키 */
const RECENT_KEY = 'hs_recent_searches'

/* ── 유틸 ─────────────────────────────── */

function isTickerLike(value) {
  return /^[A-Z0-9.-]{1,10}$/.test(value)
}

function toSearchCandidate(item) {
  return {
    ticker: item.ticker,
    name: item.name ?? item.ticker,
    sector: item.type ?? '미국 주식',
  }
}

function candidateForTicker(ticker, matches = []) {
  return matches.find((item) => item.ticker === ticker) ?? TICKER_META[ticker] ?? {
    ticker,
    name: ticker,
    sector: '미국 주식',
  }
}

function candidateMatches(item, normalized) {
  return (
    item.ticker.includes(normalized) ||
    item.name.toUpperCase().includes(normalized)
  )
}

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

function herdReadiness(data) {
  if (!data) {
    return {
      label: '계산 필요',
      tone: 'Pending',
      desc: 'HERD 계산 대기',
    }
  }
  if (shouldShowQuality(data)) {
    return {
      label: '데이터 부족',
      tone: 'Limited',
      desc: qualityReasonText(data),
    }
  }
  return {
    label: 'HERD 준비됨',
    tone: 'Ready',
    desc: data.scoreDate ?? '최신 점수',
  }
}

function inclusionDecision(data) {
  if (!data) {
    return {
      label: '계산 대기',
      desc: 'HERD 계산 후 편입 가능',
      tone: 'Pending',
    }
  }

  const readiness = herdReadiness(data)
  if (readiness.tone === 'Limited') {
    return {
      label: '보류',
      desc: '데이터 품질 확인 필요',
      tone: 'Limited',
    }
  }

  switch (normalizeStage(data.herdStage)) {
    case 'flee':
    case 'scatter':
      return {
        label: '매수 대기열',
        desc: '관심종목 우선 편입',
        tone: 'Ready',
      }
    case 'drift':
    case 'rush':
      return {
        label: '쏠림 관찰',
        desc: '신규 매수보다 관찰 우선',
        tone: 'Limited',
      }
    default:
      return {
        label: '관찰',
        desc: '보유/대기 판단 가능',
        tone: 'Neutral',
      }
  }
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
  const { user } = useAuth()
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
  const [addError, setAddError] = useState('')

  /* 최근 검색 (localStorage에서 초기값 로드) */
  const [recentSearches, setRecentSearches] = useState(loadRecent)
  const [portfolioTickers, setPortfolioTickers] = useState(new Set())
  const [watchlistTickers, setWatchlistTickers] = useState(new Set())
  const [modalTicker, setModalTicker] = useState(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  /* ── 중복 추가 방지를 위한 보유/관심 티커 조회 ── */
  useEffect(() => {
    async function fetchMembership() {
      const [portfolioRes, watchlistRes] = await Promise.allSettled([
        getPortfolio(),
        getWatchlist(),
      ])

      if (portfolioRes.status === 'fulfilled') {
        const list = portfolioRes.value.data?.data ?? []
        setPortfolioTickers(new Set(list.map(item => item.ticker)))
      }
      if (watchlistRes.status === 'fulfilled') {
        const list = watchlistRes.value.data?.data ?? []
        setWatchlistTickers(new Set(list.map(item => item.ticker)))
      }
    }
    fetchMembership()
  }, [])

  /* ── 검색 디바운스 300ms ── */
  useEffect(() => {
    /* 2글자 미만이면 드롭다운 닫기 */
    if (query.length < 2) {
      setSearchResult(null)
      return
    }

    const rawQuery = query.trim()
    const normalized = rawQuery.toUpperCase()
    const matches = STOCK_CANDIDATES.filter((item) => candidateMatches(item, normalized))

    setSearchResult({ status: 'loading', matches })
    let cancelled = false

    const timer = setTimeout(async () => {
      try {
        let candidates = matches
        try {
          const searchRes = await searchStocks(rawQuery)
          const apiResults = searchRes.data?.data?.results ?? []
          if (Array.isArray(apiResults) && apiResults.length > 0) {
            candidates = apiResults.map(toSearchCandidate)
          }
        } catch {
          // 검색 API 실패 시 로컬 후보 또는 정확한 티커 입력으로 fallback
        }

        const exact = candidates.find((item) => item.ticker === normalized)
        const ticker = exact?.ticker ?? candidates[0]?.ticker ?? (isTickerLike(normalized) ? normalized : null)
        if (!ticker) {
          if (!cancelled) setSearchResult({ status: 'not_found', matches: candidates })
          return
        }

        try {
          const res  = await getStockHerd(ticker)
          if (cancelled) return   /* 언마운트 또는 query 변경으로 취소된 경우 무시 */
          const data = res.data?.data
          if (data) {
            setSearchResult({ status: 'found', data, matches: candidates })
            /* 결과 있을 때만 최근 검색에 저장 */
            saveToRecent(ticker)
            setRecentSearches(loadRecent())
          } else {
            setSearchResult({
              status: 'symbol_found',
              candidate: candidateForTicker(ticker, candidates),
              matches: candidates,
            })
          }
        } catch {
          if (!cancelled) {
            setSearchResult({
              status: 'symbol_found',
              candidate: candidateForTicker(ticker, candidates),
              matches: candidates,
            })
          }
        }
      } catch {
        if (!cancelled) setSearchResult({ status: 'not_found', matches })
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
    const ticker = searchResult?.data?.ticker ?? searchResult?.candidate?.ticker
    setPortfolioStatus(ticker && portfolioTickers.has(ticker) ? 'exists' : 'idle')
    setWatchlistStatus(ticker && watchlistTickers.has(ticker) ? 'exists' : 'idle')
    setAddError('')
  }, [searchResult?.data?.ticker, searchResult?.candidate?.ticker, portfolioTickers, watchlistTickers])

  /* ── 추가 버튼 핸들러 ── */
  async function handleAddPortfolio(ticker) {
    if (portfolioStatus !== 'idle') return
    setAddError('')
    setPortfolioStatus('loading')
    try {
      await addToPortfolio(ticker)
      setPortfolioStatus('added')
      setPortfolioTickers(prev => new Set([...prev, ticker]))
      clearPortfolioCaches(user?.id)
      setModalTicker(ticker)
    } catch (e) {
      setPortfolioStatus(e.response?.status === 409 ? 'exists' : 'idle')
      if (e.response?.status !== 409) {
        setAddError(e.response?.data?.message ?? '종목을 추가할 수 없습니다.')
      }
    }
  }

  async function handleAddWatchlist(ticker) {
    if (watchlistStatus !== 'idle') return
    setAddError('')
    setWatchlistStatus('loading')
    try {
      await addToWatchlist(ticker)
      setWatchlistStatus('added')
      setWatchlistTickers(prev => new Set([...prev, ticker]))
    } catch (e) {
      setWatchlistStatus(e.response?.status === 409 ? 'exists' : 'idle')
      if (e.response?.status !== 409) {
        setAddError(e.response?.data?.message ?? '종목을 추가할 수 없습니다.')
      }
    }
  }

  /* 최근 검색 클릭 → 검색창에 자동 입력 */
  function handleRecentClick(ticker) {
    setQuery(ticker)
    inputRef.current?.focus()
  }

  /* 드롭다운 표시 여부 */
  const showDropdown = query.length >= 2 && searchResult !== null

  const suggestionMatches = useMemo(() => {
    const normalized = query.trim().toUpperCase()
    if (normalized.length < 2) return []
    const resultMatches = searchResult?.matches
    if (Array.isArray(resultMatches) && resultMatches.length > 0) {
      return resultMatches.slice(0, 5)
    }
    return STOCK_CANDIDATES.filter((item) => candidateMatches(item, normalized)).slice(0, 5)
  }, [query, searchResult?.matches])

  /* ── 드롭다운 콘텐츠 렌더 헬퍼 ── */
  function renderDropdownContent() {
    if (searchResult.status === 'loading') {
      return (
        <div className={styles.dropdownPlaceholder}>
          검색 중…
        </div>
      )
    }

    if (searchResult.status === 'not_found') {
      return (
        <div className={styles.dropdownPlaceholder}>
          검색 결과가 없습니다. 티커를 직접 입력해보세요.
        </div>
      )
    }

    if (searchResult.status === 'symbol_found') {
      const d = searchResult.candidate
      const readiness = herdReadiness(null)
      const decision = inclusionDecision(null)
      return (
        <div className={styles.searchResultItem}>
          <div className={styles.resultLeft}>
            <StockAvatar ticker={d.ticker} />
            <div>
              <div className={styles.resultTicker}>{d.ticker}</div>
              <div className={styles.resultName}>
                {d.name} · {d.sector}
              </div>
              <div className={styles.resultNote}>
                심볼은 찾았지만 HERD 데이터는 아직 없습니다. 상장 기간이 짧거나 계산 대기 중일 수 있어요.
              </div>
            </div>
          </div>

          <div className={styles.resultRight} onClick={e => e.stopPropagation()}>
            <div className={styles.resultHerd}>
              <div className={styles.resultHerdScore}>—</div>
              <div className={`${styles.readinessPill} ${styles.readinessPending}`}>
                {readiness.label}
              </div>
              <div className={styles.resultHerdDesc}>{readiness.desc}</div>
            </div>
            <div className={styles.resultDecision}>
              <span>편입 판단</span>
              <strong>{decision.label}</strong>
              <em>{decision.desc}</em>
            </div>
            <button
              className={`${styles.resultAddBtn} ${styles.resultAddBtnBlocked}`}
              disabled
            >
              HERD 필요
            </button>
            <button
              className={`${styles.resultAddBtn} ${styles.resultAddBtnBlocked}`}
              disabled
            >
              HERD 필요
            </button>
          </div>
        </div>
      )
    }

    /* status === 'found' */
    const d     = searchResult.data
    const color = stageColor(d.herdStage)
    const badge = badgeColors(d.herdStage)
    const meta  = searchResult.matches?.find((item) => item.ticker === d.ticker) ?? TICKER_META[d.ticker]
    const readiness = herdReadiness(d)
    const decision = inclusionDecision(d)

    return (
      <div
        className={styles.searchResultItem}
        onClick={() => navigate(`/stock/${d.ticker}`)}
      >
        {/* 좌: 배지 + 티커/종목명 */}
        <div className={styles.resultLeft}>
          <StockAvatar ticker={d.ticker} logoUrl={d.logoUrl} tone={badge} />
          <div>
            <div className={styles.resultTicker}>{d.ticker}</div>
            <div className={styles.resultName}>
              {meta ? `${meta.name} · ${meta.sector}` : '미국 주식'}
            </div>
          </div>
        </div>

        {/* 우: HERD 점수 + 추가 버튼 (이벤트 버블링 차단하여 상세 이동 방지) */}
        <div className={styles.resultRight} onClick={e => e.stopPropagation()}>
          <div className={styles.resultHerd}>
            <div className={styles.resultHerdScore} style={{ color }}>
              {Math.round(d.herdV4 ?? d.herdScore)}
            </div>
            <div className={`${styles.readinessPill} ${styles[`readiness${readiness.tone}`]}`}>
              {readiness.label}
            </div>
            <div className={styles.resultHerdDesc}>
              {stageDisplay(d.herdStage)} · {readiness.desc}
            </div>
          </div>

          <div className={`${styles.resultDecision} ${styles[`decision${decision.tone}`]}`}>
            <span>편입 판단</span>
            <strong>{decision.label}</strong>
            <em>{decision.desc}</em>
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
          {addError && <div className={styles.resultError}>{addError}</div>}
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
          HERD 계산 가능한 종목을 찾아 포트폴리오나 매수 대기열에 추가하세요
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
          {renderDropdownContent()}
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
