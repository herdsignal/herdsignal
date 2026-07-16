import { useEffect, useRef, useState } from 'react'
import { useActionNotifications } from '../../hooks/useActionNotifications'
import styles from './ActionNotifications.module.css'

export default function ActionNotifications() {
  const [open, setOpen] = useState(false)
  const [acknowledged, setAcknowledged] = useState(false)
  const panelRef = useRef(null)
  const { changes, summary, loading } = useActionNotifications()

  useEffect(() => {
    if (!open) return undefined
    const close = (event) => {
      if (!panelRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [open])

  const toggle = () => {
    setOpen((value) => !value)
    if (!open) setAcknowledged(true)
  }

  return (
    <div className={styles.root} ref={panelRef}>
      <button
        type="button"
        className={styles.trigger}
        onClick={toggle}
        aria-expanded={open}
        aria-label="행동 알림"
      >
        <span>오늘의 행동 요약</span>
        {!acknowledged && changes.length > 0 && <em>{changes.length}</em>}
      </button>

      {open && (
        <section className={styles.panel}>
          <header>
            <strong>오늘의 기준</strong>
            <span>{summary.total}종목</span>
          </header>
          <div className={styles.summary}>
            <span><b>{summary.buy}</b> 매수 관찰</span>
            <span><b>{summary.hold}</b> 유지</span>
            <span><b>{summary.reduce}</b> 축소 관찰</span>
          </div>
          <div className={styles.changes}>
            {loading && <p>판단을 확인하고 있습니다.</p>}
            {!loading && changes.length === 0 && <p>새로운 행동 변화가 없습니다.</p>}
            {changes.map((item) => (
              <article key={item.ticker}>
                <div><strong>{item.ticker}</strong><span>{item.source}</span></div>
                <p>{item.actionLabel} · {item.intensity}</p>
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
