import { useCallback, useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { getObservationChanges } from '../../api/herdApi'
import styles from './ObservationChangesIndicator.module.css'

export const OBSERVATION_CHANGES_REFRESH_EVENT = 'herdsignal:observation-changes-read'

export default function ObservationChangesIndicator() {
  const [unreadCount, setUnreadCount] = useState(null)

  const refresh = useCallback(() => {
    getObservationChanges(0)
      .then((response) => {
        setUnreadCount(Number(response.data?.data?.unreadCount) || 0)
      })
      .catch(() => setUnreadCount(null))
  }, [])

  useEffect(() => {
    refresh()
    window.addEventListener(OBSERVATION_CHANGES_REFRESH_EVENT, refresh)
    return () => {
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
