import { useCallback, useEffect, useRef, useState } from 'react'
import { getDataStatus } from '../../api/herdApi'
import { dataStatusViewModel } from './dataStatusModel'
import styles from './DataStatusIndicator.module.css'

export default function DataStatusIndicator() {
  const rootRef = useRef(null)
  const triggerRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await getDataStatus()
      setData(response.data?.data ?? null)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const reloadOnFocus = () => load()
    window.addEventListener('focus', reloadOnFocus)
    return () => window.removeEventListener('focus', reloadOnFocus)
  }, [load])

  useEffect(() => {
    if (!open) return undefined

    const closeOutside = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const view = dataStatusViewModel(data, { loading, error })

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={`${styles.trigger} ${styles[view.tone]}`}
        aria-label={`데이터 상태: ${view.label}`}
        aria-expanded={open}
        aria-controls="data-status-panel"
        aria-haspopup="dialog"
        onClick={() => setOpen((current) => !current)}
      >
        <span className={styles.dot} aria-hidden="true" />
        <span>{view.label}</span>
      </button>

      {open && (
        <section
          id="data-status-panel"
          className={styles.panel}
          role="dialog"
          aria-label="데이터 수집 상태"
        >
          <header>
            <div>
              <span>DATA STATUS</span>
              <strong>{view.label}</strong>
            </div>
            <button type="button" onClick={load} disabled={loading}>
              {loading ? '확인 중' : '새로고침'}
            </button>
          </header>

          <dl className={styles.dates}>
            <div>
              <dt>가격 기준일</dt>
              <dd>{view.priceDate}</dd>
            </div>
            <div>
              <dt>State S1 기준일</dt>
              <dd>{view.scoreDate}</dd>
            </div>
          </dl>

          <div className={styles.run}>
            <span>최근 수집</span>
            <strong>{view.runLabel}</strong>
            <small>{view.coverageLabel}</small>
          </div>
          {view.issueLabel && <p className={styles.issue}>{view.issueLabel}</p>}
        </section>
      )}
    </div>
  )
}
