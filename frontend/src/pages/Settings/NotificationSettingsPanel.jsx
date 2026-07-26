import { useState } from 'react'
import {
  canUseBrowserNotifications,
  observationNotificationsEnabled,
  setObservationNotificationsEnabled,
} from '../../utils/observationNotifications'
import styles from './Settings.module.css'

export default function NotificationSettingsPanel() {
  const supported = canUseBrowserNotifications()
  const [enabled, setEnabled] = useState(observationNotificationsEnabled)
  const [status, setStatus] = useState('')

  async function toggle() {
    if (!supported) return
    if (enabled) {
      setObservationNotificationsEnabled(false)
      setEnabled(false)
      setStatus('이 브라우저의 관찰 변화 알림을 껐습니다.')
      return
    }

    const permission = Notification.permission === 'granted'
      ? 'granted'
      : await Notification.requestPermission()
    const nextEnabled = permission === 'granted'
    setObservationNotificationsEnabled(nextEnabled)
    setEnabled(nextEnabled)
    setStatus(nextEnabled
      ? '앱 실행 중 새 State S1 변화가 생기면 알려드립니다.'
      : '브라우저 알림 권한이 허용되지 않았습니다.')
  }

  return (
    <section className={styles.panel}>
      <div className={styles.notificationRow}>
        <div>
          <span>관찰 변화 알림</span>
          <strong>State S1 미확인 변화</strong>
          <em>앱 실행 중 5분마다 확인 · 매매 추천 알림 아님</em>
        </div>
        <button type="button" onClick={toggle} disabled={!supported}>
          {!supported ? '지원 안 함' : enabled ? '켜짐' : '꺼짐'}
        </button>
      </div>
      {status && <p className={styles.notificationStatus} role="status">{status}</p>}
    </section>
  )
}
