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
import { opportunityRows } from '../../utils/portfolioTools'
import { useDashboardMarketData } from '../Dashboard/useDashboardMarketData'
import styles from './Watchlist.module.css'
import WatchlistMarketBanner from './WatchlistMarketBanner'
import WatchlistQueue from './WatchlistQueue'

const REFRESH_SCOPE_TITLE = '관심종목 HERD DB 조회와 SPY 최신 점수만 갱신합니다. 히스토리는 Timeline 탭에서 별도 조회됩니다.'

export default function Watchlist() {
  const navigate = useNavigate()
  const market = useDashboardMarketData()
  const [watchlist, setWatchlist] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshNotice, setRefreshNotice] = useState(null)
  const [error, setError] = useState(null)
  const [deletingTicker, setDeletingTicker] = useState(null)
  const refreshNoticeTimer = useRef(null)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  const fetchData = useCallback(async (silent = false) => {
    if (silent) {
      setRefreshing(true)
      clearTimeout(refreshNoticeTimer.current)
      setRefreshNotice('관심종목 HERD 조회 중')
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const listResponse = await getWatchlist().catch(() => null)
      if (!listResponse) {
        setWatchlist([])
        setError(`백엔드 서버에 연결할 수 없습니다. ${API_HOST}이 실행 중인지 확인해주세요.`)
        if (silent) setRefreshNotice('관심종목 HERD 조회 실패')
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
      if (silent) setRefreshNotice('관심종목 HERD 갱신')
    } catch {
      setWatchlist([])
      setError('관심종목의 State S1 관찰값을 불러오지 못했습니다.')
      if (silent) setRefreshNotice('관심종목 State S1 조회 실패')
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
    setDeletingTicker(ticker)
    try {
      await removeFromWatchlist(ticker)
      setWatchlist((current) => current.filter((item) => item.ticker !== ticker))
    } catch {
      // 삭제 실패 시 현재 목록을 유지한다.
    } finally {
      setDeletingTicker(null)
    }
  }

  const scoredWatchlist = useMemo(() => opportunityRows(watchlist), [watchlist])
  const opportunityQueue = useMemo(
    () => scoredWatchlist
      .filter((item) => item.signal === 'BUY' || item.signal === 'ADD')
      .slice(0, 5),
    [scoredWatchlist]
  )

  return (
    <div>
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>매수 대기열</h1>
          <p className={styles.pageDesc}>관심종목 중 HERD가 매수권에 가까운 종목부터 확인합니다.</p>
        </div>
        <div className={styles.headerActions}>
          {refreshNotice && <span className={styles.refreshNotice}>{refreshNotice}</span>}
          <button
            className={styles.btnRefresh}
            onClick={() => fetchData(true)}
            disabled={refreshing || loading}
            title={REFRESH_SCOPE_TITLE}
          >
            {refreshing ? '새로고침 중…' : '↻ 새로고침'}
          </button>
          <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
            종목 추가
          </button>
        </div>
      </div>

      <WatchlistMarketBanner {...market} />

      {loading && (
        <div className={styles.loadingState}>
          <span className={styles.loadingText}>로딩 중…</span>
        </div>
      )}

      {!loading && error && (
        <div className={styles.errorState}>
          <p className={styles.errorText}>{error}</p>
          <button className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
        </div>
      )}

      {!loading && !error && watchlist.length > 0 && (
        <WatchlistQueue
          watchlist={watchlist}
          scoredWatchlist={scoredWatchlist}
          opportunityQueue={opportunityQueue}
          deletingTicker={deletingTicker}
          onDelete={handleDelete}
          onOpenStock={(ticker) => navigate(`/stock/${ticker}`)}
        />
      )}

      {!loading && !error && watchlist.length === 0 && (
        <div className={styles.emptyState}>
          <p className={styles.emptyTitle}>관심 종목이 없습니다.</p>
          <p className={styles.emptyDesc}>종목을 검색해 추가해보세요.</p>
          <button className={styles.btnPrimary} onClick={() => navigate('/search')}>
            종목 검색
          </button>
        </div>
      )}
    </div>
  )
}
