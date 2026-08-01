import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getDataStatus,
  requestDailySchedulerRun,
  requestSchedulerRun,
} from '../../api/herdApi'
import { dataStatusViewModel } from './dataStatusModel'
import styles from './DataStatusIndicator.module.css'

export default function DataStatusIndicator() {
  const rootRef = useRef(null)
  const triggerRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [requestMessage, setRequestMessage] = useState(null)

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

  const runNow = useCallback(async (scope = 'daily') => {
    setRequesting(true)
    setRequestMessage(null)
    try {
      if (scope === 'full') await requestSchedulerRun()
      else await requestDailySchedulerRun()
      setRequestMessage(scope === 'full'
        ? '주간 전체 갱신을 시작했습니다.'
        : '일간 잠정 갱신을 시작했습니다.')
      window.setTimeout(load, 1_000)
    } catch (requestError) {
      setRequestMessage(
        requestError.response?.status === 409
          ? '이미 갱신 중입니다.'
          : '갱신 요청에 실패했습니다.',
      )
    } finally {
      setRequesting(false)
    }
  }, [load])

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

  useEffect(() => {
    if (!open) return undefined
    const intervalId = window.setInterval(load, 10_000)
    return () => window.clearInterval(intervalId)
  }, [load, open])

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
              {loading ? '확인 중' : '상태 다시 확인'}
            </button>
          </header>

          <div className={styles.schedule}>
            <span>자동 수집 예정</span>
            <strong>{view.scheduleLabel}</strong>
            <small>{view.scheduleLocalLabel}</small>
            <small>{view.automationLabel}</small>
          </div>

          <dl className={styles.dates}>
            <div>
              <dt>
                <span>가격 데이터</span>
                <small>거래일마다</small>
              </dt>
              <dd>{view.priceDate}</dd>
              <p>미국장 마감 후 반영</p>
            </div>
            <div>
              <dt>
                <span>State S1</span>
                <small>주 1회</small>
              </dt>
              <dd>{view.scoreDate}</dd>
              <p>완료된 금요일 기준</p>
            </div>
            <div>
              <dt>
                <span>Daily D1</span>
                <small>잠정</small>
              </dt>
              <dd>{view.dailyScoreDate}</dd>
              <p>{view.dailyStatusLabel} · {view.dailyCoverageLabel}</p>
            </div>
          </dl>

          <div className={styles.run}>
            <span>최근 수집</span>
            <strong>{view.runLabel}</strong>
            <small>{view.coverageLabel}</small>
          </div>
          {view.phases.length > 0 && (
            <ul className={styles.phases} aria-label="최근 실행 단계">
              {view.phases.map((phase) => (
                <li key={phase.code}>
                  <span>{phase.label}</span>
                  <strong data-status={phase.status}>{phase.statusLabel}</strong>
                  {phase.detail && <small>{phase.detail}</small>}
                </li>
              ))}
            </ul>
          )}
          {view.issueLabel && <p className={styles.issue}>{view.issueLabel}</p>}
          <details className={styles.manual}>
            <summary>수동 실행</summary>
            <p>
              일간 갱신은 가격·D1만, 주간 전체는 S1과 연구 원장까지 다시 계산합니다.
            </p>
            <div className={styles.actions}>
              <button type="button" onClick={() => runNow('daily')} disabled={requesting || view.isRunning}>
                {requesting ? '요청 중' : view.isRunning ? '갱신 중' : '일간 잠정 갱신'}
              </button>
              <button type="button" onClick={() => runNow('full')} disabled={requesting || view.isRunning}>
                주간 전체 갱신
              </button>
              {requestMessage && <span role="status">{requestMessage}</span>}
            </div>
          </details>
        </section>
      )}
    </div>
  )
}
