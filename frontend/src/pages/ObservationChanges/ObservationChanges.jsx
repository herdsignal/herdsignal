import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getObservationChanges,
  markAllObservationChangesSeen,
  markObservationTickerSeen,
} from '../../api/herdApi'
import {
  OBSERVATION_CHANGES_REFRESH_EVENT,
} from '../../components/ObservationChanges/ObservationChangesIndicator'
import StockAvatar from '../../components/StockAvatar/StockAvatar'
import {
  describeObservationChange,
  displayStage,
  formatObservationDelta,
  sortObservationChanges,
  trackingScopeLabel,
} from './observationChangesModel'
import styles from './ObservationChanges.module.css'

function dispatchChangesRead() {
  window.dispatchEvent(new Event(OBSERVATION_CHANGES_REFRESH_EVENT))
}

export default function ObservationChanges() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('unread')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [markingAll, setMarkingAll] = useState(false)

  const fetchChanges = useCallback(() => {
    setLoading(true)
    setError(null)
    getObservationChanges(100)
      .then((response) => setData(response.data?.data ?? null))
      .catch(() => setError('관찰 변화를 불러오지 못했습니다.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchChanges()
  }, [fetchChanges])

  const events = useMemo(() => {
    const sorted = sortObservationChanges(data?.events)
    return filter === 'unread'
      ? sorted.filter((event) => event.unread)
      : sorted
  }, [data?.events, filter])

  async function openEvent(event) {
    if (event.unread) {
      setData((current) => ({
        ...current,
        unreadCount: Math.max(0, current.unreadCount - 1),
        events: current.events.map((item) => (
          item.ticker === event.ticker
          && item.observationDate <= event.observationDate
            ? { ...item, unread: false }
            : item
        )),
      }))
      try {
        await markObservationTickerSeen(event.ticker, event.observationDate)
        dispatchChangesRead()
      } catch {
        fetchChanges()
        return
      }
    }
    navigate(`/stock/${event.ticker}`)
  }

  async function markAllSeen() {
    if (!data?.unreadCount || markingAll) return
    setMarkingAll(true)
    try {
      await markAllObservationChangesSeen()
      setData((current) => ({
        ...current,
        unreadCount: 0,
        events: current.events.map((event) => ({ ...event, unread: false })),
      }))
      dispatchChangesRead()
    } catch {
      setError('확인 상태를 저장하지 못했습니다.')
    } finally {
      setMarkingAll(false)
    }
  }

  return (
    <div className={styles.page} aria-busy={loading}>
      <header className={styles.header}>
        <div>
          <span>OBSERVATION CHANGES</span>
          <h1>관찰 변화</h1>
          <p>보유·관심 종목의 확인된 State S1 변화</p>
        </div>
        <div className={styles.headerMeta}>
          <span>{data?.generatedThrough ?? '—'} 기준</span>
          <button
            type="button"
            onClick={markAllSeen}
            disabled={!data?.unreadCount || markingAll}
          >
            {markingAll ? '처리 중…' : '모두 확인'}
          </button>
        </div>
      </header>

      <section className={styles.summary} aria-label="관찰 변화 요약">
        <div><span>미확인</span><strong>{data?.unreadCount ?? '—'}</strong></div>
        <div><span>추적 종목</span><strong>{data?.trackedTickerCount ?? '—'}</strong></div>
        <div className={styles.filters} aria-label="변화 필터">
          <button
            type="button"
            aria-pressed={filter === 'unread'}
            onClick={() => setFilter('unread')}
          >
            미확인
          </button>
          <button
            type="button"
            aria-pressed={filter === 'all'}
            onClick={() => setFilter('all')}
          >
            전체
          </button>
        </div>
      </section>

      {loading && <div className={styles.statePanel} role="status">변화 확인 중…</div>}
      {!loading && error && (
        <div className={styles.statePanel} role="alert">
          <p>{error}</p>
          <button type="button" onClick={fetchChanges}>다시 시도</button>
        </div>
      )}
      {!loading && !error && events.length === 0 && (
        <div className={styles.emptyState}>
          <span>{filter === 'unread' ? 'ALL SEEN' : 'NO RECENT CHANGE'}</span>
          <h2>{filter === 'unread' ? '확인할 변화가 없습니다.' : '최근 변화가 없습니다.'}</h2>
        </div>
      )}
      {!loading && !error && events.length > 0 && (
        <section className={styles.list} aria-label="State S1 변화 목록">
          {events.map((event) => (
            <button
              type="button"
              key={event.id}
              className={styles.row}
              data-unread={event.unread}
              onClick={() => openEvent(event)}
            >
              <span className={styles.identity}>
                <StockAvatar
                  ticker={event.ticker}
                  logoUrl={event.logoUrl}
                  size="md"
                />
                <span>
                  <strong>{event.ticker}</strong>
                  <small>{event.companyName ?? event.sector ?? '미국 주식'}</small>
                </span>
              </span>
              <span className={styles.change}>
                <strong>{describeObservationChange(event)}</strong>
                <small>
                  {trackingScopeLabel(event.trackingScope)}
                  {' · '}
                  {event.eventType === 'TRANSITION'
                    ? `${displayStage(event.stage)} · 상태 전환`
                    : '단계 경계 통과'}
                </small>
              </span>
              <span className={styles.score}>
                <strong>{Math.round(Number(event.stateScore))}</strong>
                <small>4주 {formatObservationDelta(event.delta4w)}</small>
              </span>
              <span className={styles.date}>
                <strong>{event.observationDate}</strong>
                <small>{event.unread ? '미확인' : '확인'}</small>
              </span>
            </button>
          ))}
        </section>
      )}
    </div>
  )
}
