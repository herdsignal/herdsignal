import { useState } from 'react'
import styles from './Dashboard.module.css'

export const DASHBOARD_ONBOARDING_KEY = 'herdsignal_dashboard_onboarding_v1'

export default function DashboardOnboarding() {
  const [visible, setVisible] = useState(
    () => localStorage.getItem(DASHBOARD_ONBOARDING_KEY) !== 'done',
  )

  if (!visible) return null

  function dismiss() {
    localStorage.setItem(DASHBOARD_ONBOARDING_KEY, 'done')
    setVisible(false)
  }

  return (
    <aside className={styles.onboarding} aria-label="대시보드 사용 순서">
      <ol>
        <li><span>1</span><strong>티커 검색</strong></li>
        <li><span>2</span><strong>HERD 위치 확인</strong></li>
        <li><span>3</span><strong>이력 확인</strong></li>
      </ol>
      <button type="button" onClick={dismiss} aria-label="사용 순서 닫기">
        확인
      </button>
    </aside>
  )
}
