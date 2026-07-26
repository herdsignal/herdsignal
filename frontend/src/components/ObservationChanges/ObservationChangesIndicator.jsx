import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { getObservationChanges } from '../../api/herdApi'
import { useAuth } from '../../auth/AuthContext'
import {
  canUseBrowserNotifications,
  observationNotificationsEnabled,
  shouldNotifyObservationChange,
} from '../../utils/observationNotifications'
import styles from './ObservationChangesIndicator.module.css'

export const OBSERVATION_CHANGES_REFRESH_EVENT = 'herdsignal:observation-changes-read'
const POLL_INTERVAL_MS = 5 * 60 * 1000

export default function ObservationChangesIndicator() {
  const { user } = useAuth()
  const userId = user?.id
  const [unreadCount, setUnreadCount] = useState(null)
  const previousCount = useRef(null)

  const refresh = useCallback(() => {
    getObservationChanges(0)
      .then((response) => {
        const nextCount = Number(response.data?.data?.unreadCount) || 0
        if (
          canUseBrowserNotifications()
          && shouldNotifyObservationChange(
            previousCount.current,
            nextCount,
            observationNotificationsEnabled(userId),
            Notification.permission,
          )
        ) {
          try {
            new Notification('HerdSignal 관찰 변화', {
              body: `새 State S1 변화 ${nextCount - previousCount.current}건`,
            })
          } catch {
            // OS 알림 실패가 상단 미확인 개수 갱신을 막지 않는다.
          }
        }
        previousCount.current = nextCount
        setUnreadCount(nextCount)
      })
      .catch(() => setUnreadCount(null))
  }, [userId])

  useEffect(() => {
    refresh()
    const interval = window.setInterval(refresh, POLL_INTERVAL_MS)
    window.addEventListener(OBSERVATION_CHANGES_REFRESH_EVENT, refresh)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener(OBSERVATION_CHANGES_REFRESH_EVENT, refresh)
    }
  }, [refresh])

  const label = unreadCount > 0
    ? `관찰 변화 ${unreadCount}개 미확인`
    : '관찰 변화'

  return (
    <NavLink className={styles.link} to="/changes" aria-label={label}>
      <span>변화</span>
      {unreadCount > 0 && (
        <strong aria-hidden="true">{unreadCount > 99 ? '99+' : unreadCount}</strong>
      )}
    </NavLink>
  )
}
