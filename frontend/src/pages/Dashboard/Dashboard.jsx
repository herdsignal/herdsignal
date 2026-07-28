import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import HerdObservationPanel from '../../components/HerdObservationPanel/HerdObservationPanel'
import TickerSearch from '../../components/TickerSearch/TickerSearch'
import AvgPriceModal from '../../components/AvgPriceModal/AvgPriceModal'
import { useAuth } from '../../auth/AuthContext'
import PortfolioHistory from '../Portfolio/PortfolioHistory'
import PortfolioHoldings from '../Portfolio/PortfolioHoldings'
import { usePortfolioPageData } from '../Portfolio/usePortfolioPageData'
import {
  STOCK_CANDIDATES,
  TICKER_META,
  candidateMatches,
} from '../Search/searchModel'
import { useStockSearch } from '../Search/useStockSearch'
import { useTickerMembership } from '../Search/useTickerMembership'
import { useMarketHomeData } from '../MarketHome/useMarketHomeData'
import { marketHomeViewModel } from '../MarketHome/marketHomeModel'
import styles from './Dashboard.module.css'
import DashboardOnboarding from './DashboardOnboarding'

function resultTicker(result) {
  return result?.data?.ticker ?? result?.candidate?.ticker ?? null
}

function resultMeta(result) {
  const ticker = resultTicker(result)
  if (!ticker) return null
  return result?.matches?.find((item) => item.ticker === ticker)
    ?? TICKER_META[ticker]
    ?? { ticker, name: ticker, sector: '미국 주식' }
}

function selectedObservation(result) {
  if (result?.status !== 'found') return null
  return {
    ticker: result.data.ticker,
    name: resultMeta(result)?.name ?? result.data.ticker,
    score: result.data.herdScore,
    stage: result.data.herdStage,
    delta4w: result.data.delta4w,
    observationDate: result.data.scoreDate,
    freshness: result.data.freshnessStatus === 'STALE' ? '주간 관찰 갱신 필요' : '주간 관찰',
  }
}

export default function Dashboard() {
  const { user } = useAuth()
  const authenticated = Boolean(user?.authenticated)
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [assetsOpen, setAssetsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeStock, setActiveStock] = useState(null)
  const [searchRequested, setSearchRequested] = useState(false)
  const { searchResult, recentSearches } = useStockSearch(query)
  const candidate = resultMeta(searchResult)
  const candidateTicker = resultTicker(searchResult)
  const market = marketHomeViewModel(useMarketHomeData())
  const portfolio = usePortfolioPageData({
    assetHistoryInitiallyOpen: false,
    enabled: authenticated,
  })
  const membership = useTickerMembership({
    selectedTicker: candidateTicker,
    userId: user?.id,
    enabled: authenticated,
  })

  const suggestions = useMemo(() => {
    const normalized = query.trim().toUpperCase()
    if (normalized.length < 2) return []
    const matches = searchResult?.matches?.length
      ? searchResult.matches
      : STOCK_CANDIDATES.filter((item) => candidateMatches(item, normalized))
    return matches.slice(0, 5)
  }, [query, searchResult?.matches])

  const selected = activeStock ?? {
    ticker: 'SPY',
    name: 'S&P 500',
    score: market.score,
    stage: market.stage,
    delta4w: market.delta4w,
    observationDate: market.observationDate,
    freshness: market.freshness,
  }
  const showingMarket = selected.ticker === 'SPY'
  const totalAsset = portfolio.summary?.total_asset_value
    ?? portfolio.summary?.total_value
  const invested = portfolio.summary?.invested_value

  function showCandidateHerd() {
    const next = selectedObservation(searchResult)
    if (!next) {
      setSearchRequested(true)
      return
    }
    setActiveStock(next)
    setSearchRequested(false)
  }

  function changeQuery(nextQuery) {
    setQuery(nextQuery)
    setSearchRequested(false)
  }

  function selectAndShow(ticker) {
    setQuery(ticker)
    setSearchRequested(true)
  }

  function toggleAssets() {
    setAssetsOpen((open) => {
      const next = !open
      portfolio.setAssetPanelOpen(next)
      return next
    })
  }

  useEffect(() => {
    if (!searchRequested || searchResult?.status !== 'found') return
    const next = selectedObservation(searchResult)
    if (!next) return
    setActiveStock(next)
    setSearchRequested(false)
  }, [searchRequested, searchResult])

  return (
    <div className={styles.page}>
      <section id="stock-search" className={styles.finder} aria-label="종목 검색">
        <TickerSearch
          ref={inputRef}
          size="large"
          query={query}
          suggestions={
            candidateTicker === query.trim().toUpperCase() ? [] : suggestions
          }
          onQueryChange={changeQuery}
          onSubmit={showCandidateHerd}
          recentTickers={recentSearches}
          onRecentSelect={selectAndShow}
          onSuggestionSelect={(item) => {
            selectAndShow(item.ticker)
          }}
        />
        <DashboardOnboarding />

        {query.trim().length >= 2 && searchResult && (
          <div className={styles.searchState} role="status">
            {searchResult.status === 'loading' && (
              <span>{searchRequested ? 'HERD 불러오는 중…' : '검색 중…'}</span>
            )}
            {searchResult.status === 'not_found' && <span>검색 결과가 없습니다.</span>}
            {(searchResult.status === 'found' || searchResult.status === 'symbol_found') && (
              <>
                <div>
                  <strong>{candidateTicker}</strong>
                  <span>{candidate?.name}</span>
                  {searchResult.status === 'symbol_found' && <small>HERD 관찰 준비 중</small>}
                </div>
                <div>
                  <button
                    type="button"
                    disabled={searchResult.status !== 'found'}
                    onClick={showCandidateHerd}
                  >
                    HERD 보기
                  </button>
                  <button
                    type="button"
                    hidden={!authenticated}
                    disabled={[
                      'loading',
                      'added',
                      'exists',
                    ].includes(membership.watchlistStatus)}
                    onClick={() => membership.handleAddWatchlist(candidateTicker)}
                  >
                    {membership.watchlistStatus === 'added'
                      ? '관심 종목 추가됨'
                      : membership.watchlistStatus === 'exists'
                        ? '관심 종목'
                        : '관심 종목 추가'}
                  </button>
                </div>
              </>
            )}
            {membership.addError && <p role="alert">{membership.addError}</p>}
          </div>
        )}
      </section>

      <HerdObservationPanel
        compact
        condensed
        ticker={selected.ticker}
        name={selected.name}
        scopeLabel={showingMarket ? 'S&P 500 MARKET' : 'INDIVIDUAL STOCK'}
        score={selected.score}
        stage={selected.stage}
        delta4w={selected.delta4w}
        observationDate={selected.observationDate}
        freshness={selected.freshness}
        loading={showingMarket && market.loading}
        unavailable={showingMarket ? market.unavailable : selected.score == null}
        error={showingMarket && market.observationError}
        actions={(
          <>
            {!showingMarket && (
              <button type="button" onClick={() => setActiveStock(null)}>SPY로 돌아가기</button>
            )}
            <Link to={`/stock/${selected.ticker}`}>종목 상세 보기</Link>
          </>
        )}
      />

      <section className={styles.portfolioSection} aria-label="보유 현황">
        {!authenticated ? (
          <div className={styles.empty}>
            <p>포트폴리오와 관심 종목은 로그인 후 저장됩니다.</p>
            <Link to="/login">Google로 로그인</Link>
          </div>
        ) : (
          <>
        <header>
          <div>
            <span>PORTFOLIO OBSERVATION</span>
            <h2>보유 현황</h2>
          </div>
          <div className={styles.portfolioTools}>
            <small>{portfolio.sortedRows.length}개 종목</small>
            <button
              type="button"
              className={styles.assetToggle}
              aria-expanded={assetsOpen}
              aria-controls="dashboard-assets"
              onClick={toggleAssets}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 7.5h16v11H4zM7 7.5V5.8A1.8 1.8 0 0 1 8.8 4h7.4A1.8 1.8 0 0 1 18 5.8v1.7M16 13h4" />
                <circle cx="16" cy="13" r=".8" />
              </svg>
              <span>{assetsOpen ? '자산 닫기' : '내 자산 보기'}</span>
            </button>
          </div>
        </header>

        {assetsOpen && (
          <section id="dashboard-assets" className={styles.assets} aria-label="내 자산">
            <div className={styles.assetSummary}>
              <span>전체 자산</span>
              <strong>{portfolio.displayAmount(totalAsset)}</strong>
              <dl>
                <div>
                  <dt>주식 평가액</dt>
                  <dd>{portfolio.displayAmount(invested)}</dd>
                </div>
                <div>
                  <dt>현금</dt>
                  <dd>{portfolio.displayAmount(portfolio.cashBalance)}</dd>
                </div>
              </dl>
              <div className={styles.assetControls}>
                {['KRW', 'USD'].map((mode) => (
                  <button
                    type="button"
                    key={mode}
                    aria-pressed={portfolio.currencyMode === mode}
                    onClick={() => portfolio.selectCurrency(mode)}
                  >
                    {mode}
                  </button>
                ))}
                <button type="button" onClick={portfolio.togglePrivacyMode}>
                  {portfolio.privacyMode ? '금액 보기' : '금액 가리기'}
                </button>
              </div>
            </div>
            <PortfolioHistory
              points={portfolio.assetChartHistory}
              period={portfolio.assetHistoryPeriod}
              periodLabel={portfolio.assetPeriodLabel}
              accountValueChangePct={portfolio.accountValueChangePct}
              loading={portfolio.assetHistoryLoading}
              error={portfolio.assetHistoryError}
              displayAmount={portfolio.displayAmount}
              privacyMode={portfolio.privacyMode}
              onPeriodChange={portfolio.setAssetHistoryPeriod}
            />
          </section>
        )}

        {portfolio.loading && <p role="status">포트폴리오 불러오는 중…</p>}
        {!portfolio.loading && portfolio.error && (
          <div role="alert">
            <p>{portfolio.error}</p>
            <button type="button" onClick={portfolio.fetchData}>다시 시도</button>
          </div>
        )}
        {!portfolio.loading && !portfolio.error && portfolio.sortedRows.length === 0 && (
          <div className={styles.empty}>
            <p>아직 보유 종목이 없습니다.</p>
            <button type="button" onClick={() => inputRef.current?.focus()}>종목 찾기</button>
          </div>
        )}
        {!portfolio.loading && !portfolio.error && portfolio.sortedRows.length > 0 && (
          <PortfolioHoldings
            rows={portfolio.sortedRows}
            sortBy={portfolio.sortBy}
            deletingTicker={portfolio.deletingTicker}
            displayAmount={portfolio.displayAmount}
            displaySignedAmount={portfolio.displaySignedAmount}
            onSortChange={portfolio.selectSort}
            onOpenStock={(ticker) => navigate(`/stock/${ticker}`)}
            onEditHolding={portfolio.setModalTicker}
            onDelete={portfolio.handleDelete}
            onTargetWeightSave={portfolio.handleTargetWeightSave}
            targetSavingTicker={portfolio.targetSavingTicker}
          />
        )}

        {portfolio.modalTicker && (
          <AvgPriceModal
            ticker={portfolio.modalTicker}
            currentAvgPrice={portfolio.modalStock?.avgPrice ?? null}
            currentQuantity={portfolio.modalStock?.quantity ?? null}
            onClose={() => portfolio.setModalTicker(null)}
            onSaved={portfolio.handleModalSaved}
          />
        )}
          </>
        )}
      </section>
    </div>
  )
}
