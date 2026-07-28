import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getHerdObservations,
  getWatchlist,
  removeFromWatchlist,
} from '../../api/herdApi'
import { API_HOST } from '../../utils/apiConfig'
import {
  observationBatchToMap,
  observationToTrackedItem,
} from '../../utils/herdObservation'
import styles from './Watchlist.module.css'
import WatchlistQueue from './WatchlistQueue'
import {
  selectUnavailableWatchlistItems,
  WATCHLIST_SORTS,
  sortWatchlistObservations,
  summarizeWatchlistStages,
} from './watchlistModel'

export default function Watchlist() {
  const navigate = useNavigate()
  const [watchlist, setWatchlist] = useState([])
  const [sortBy, setSortBy] = useState('recent')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshNotice, setRefreshNotice] = useState(null)
  const [error, setError] = useState(null)
  const [deleteError, setDeleteError] = useState(null)
  const [deletingTicker, setDeletingTicker] = useState(null)
  const refreshNoticeTimer = useRef(null)

  const fetchData = useCallback(async (silent = false) => {
    if (silent) {
      setRefreshing(true)
      clearTimeout(refreshNoticeTimer.current)
      setRefreshNotice('저장된 State S1 불러오는 중')
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const listResponse = await getWatchlist().catch(() => null)
      if (!listResponse) {
        setWatchlist([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
        return
      }
      const rawItems = Array.isArray(listResponse.data?.data)
        ? listResponse.data.data
        : []
      const extras = Object.fromEntries(
        rawItems.map((item) => [item.ticker, item]),
      )
      const tickers = rawItems.map((item) => item.ticker)
      const batchResponse = tickers.length > 0
        ? await getHerdObservations(tickers)
        : null
      const observationMap = observationBatchToMap(
        batchResponse?.data?.data,
        extras,
      )
      setWatchlist(rawItems.map((item) => (
        observationMap[item.ticker]
        ?? observationToTrackedItem(null, item)
      )))
      if (silent) setRefreshNotice('최신 저장값을 불러왔습니다')
    } catch {
      setError('관심종목의 State S1 관찰값을 불러오지 못했습니다.')
      if (silent) setRefreshNotice('State S1 조회 실패')
    } finally {
      setLoading(false)
      setRefreshing(false)
      if (silent) {
        refreshNoticeTimer.current = setTimeout(() => setRefreshNotice(null), 3200)
      }
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])
  useEffect(() => () => clearTimeout(refreshNoticeTimer.current), [])

  async function handleDelete(event, ticker) {
    event.stopPropagation()
    if (deletingTicker) return
    setDeleteError(null)
    setDeletingTicker(ticker)
    try {
      await removeFromWatchlist(ticker)
      setWatchlist((current) => current.filter((item) => item.ticker !== ticker))
    } catch {
      setDeleteError(`${ticker} 관심종목을 삭제하지 못했습니다.`)
    } finally {
      setDeletingTicker(null)
    }
  }

  const sortedWatchlist = useMemo(
    () => sortWatchlistObservations(watchlist, sortBy),
    [sortBy, watchlist],
  )
  const stageSummary = useMemo(
    () => summarizeWatchlistStages(watchlist),
    [watchlist],
  )
  const unavailableItems = useMemo(
    () => selectUnavailableWatchlistItems(watchlist),
    [watchlist],
  )

  return (
    <div className={styles.page} aria-busy={loading || refreshing}>
      <header className={styles.pageHeader}>
        <div>
          <span>WATCH FIELD</span>
          <h1>관심종목</h1>
          <p>저장한 종목의 HERD 위치와 4주 변화를 봅니다.</p>
        </div>
        <div className={styles.headerActions}>
          {refreshNotice && <span role="status">{refreshNotice}</span>}
          <button
            type="button"
            onClick={() => fetchData(true)}
            disabled={refreshing || loading}
          >
            {refreshing ? '불러오는 중…' : '다시 불러오기'}
          </button>
          <button type="button" onClick={() => navigate('/app#stock-search')}>종목 추가</button>
        </div>
      </header>

      {deleteError && <p className={styles.inlineError} role="alert">{deleteError}</p>}
      {loading && <div className={styles.statePanel} role="status">관심종목 불러오는 중…</div>}
      {!loading && error && (
        <div className={styles.statePanel} role="alert">
          <p>{error}</p>
          <button type="button" onClick={fetchData}>다시 시도</button>
        </div>
      )}
      {!loading && !error && watchlist.length === 0 && (
        <div className={styles.emptyState}>
          <span>EMPTY WATCH FIELD</span>
          <h2>관찰할 종목을 추가해보세요.</h2>
          <button type="button" onClick={() => navigate('/app#stock-search')}>종목 찾기</button>
        </div>
      )}
      {!loading && !error && watchlist.length > 0 && (
        <>
          <section className={styles.stageSummary} aria-label="관심종목 HERD 분포">
            {stageSummary.map((item) => (
              <div key={item.stage}>
                <i style={{ background: item.color }} />
                <span>{item.stage}</span>
                <strong>{item.count}</strong>
              </div>
            ))}
          </section>
          {unavailableItems.length > 0 && (
            <section className={styles.pendingPanel} aria-label="State S1 관찰 준비 중인 종목">
              <div>
                <span>관찰 준비 중</span>
                <strong>{unavailableItems.map((item) => item.ticker).join(' · ')}</strong>
              </div>
              <p>
                저장은 유지됩니다. 충분한 가격 이력과 자산별 비교 기준이 확인되면 State S1에 포함됩니다.
              </p>
            </section>
          )}
          <div className={styles.listHeader}>
            <span>{watchlist.length}개 종목</span>
            <div aria-label="관심종목 정렬">
              {WATCHLIST_SORTS.map((item) => (
                <button
                  type="button"
                  key={item.value}
                  aria-pressed={sortBy === item.value}
                  className={sortBy === item.value ? styles.activeSort : ''}
                  onClick={() => setSortBy(item.value)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <WatchlistQueue
            watchlist={sortedWatchlist}
            deletingTicker={deletingTicker}
            onDelete={handleDelete}
            onOpenStock={(ticker) => navigate(`/stock/${ticker}`)}
          />
        </>
      )}
    </div>
  )
}
