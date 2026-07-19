/**
 * HerdLab.jsx — HERD Index 검증 데이터 보드 (/herd-lab)
 */

import { useEffect, useState } from 'react'
import { getModelValidationReport, getShadowModelStatus } from '../../api/herdApi'
import herdModelReport from '../../data/herdModelReport'
import styles from './HerdLab.module.css'
import { presentValidationReport } from './herdModelPresentation'
import { presentShadowStatus } from './shadowModelPresentation'
import { ActionOutcomesPanel, MethodologyPanel, ValidationPanel } from './HerdLabSections'

const { model: MODEL_BASE } = herdModelReport

export default function HerdLab() {
  const [report, setReport] = useState(null)
  const [shadow, setShadow] = useState(() => presentShadowStatus(null))
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.allSettled([getModelValidationReport(), getShadowModelStatus()])
      .then(([validationResult, shadowResult]) => {
        if (!active) return
        if (validationResult.status === 'rejected') {
          throw validationResult.reason
        }
        setReport(presentValidationReport(validationResult.value.data.data))
        if (shadowResult.status === 'fulfilled') {
          setShadow(presentShadowStatus(shadowResult.value.data.data))
        }
      })
      .catch((requestError) => {
        if (active) setError(requestError.response?.data?.message || '검증 리포트를 불러오지 못했습니다.')
      })
    return () => { active = false }
  }, [])

  if (error) {
    return <div className={styles.page}><section className={styles.panel} role="alert"><p className={styles.inlineStatus}>{error}</p></section></div>
  }

  if (!report) {
    return <div className={styles.page}><p>최신 검증 리포트를 불러오는 중입니다.</p></div>
  }

  const { model, metrics, trustChecks, modelNotes, rows, featuredSectors, actionOutcomes } = report

  return (
    <div className={styles.page}>
      <section className={styles.overview}>
        <header>
          <span>HERD LAB · {model.status}</span>
          <h1>{model.version}</h1>
          <p>{MODEL_BASE.name} · {model.generatedAt} 갱신</p>
          <div className={`${styles.shadowStatus} ${styles[shadow.tone]}`}>
            <i />
            <span>{shadow.label}</span>
            {shadow.candidate && <strong>{shadow.candidate}</strong>}
          </div>
        </header>
        <div className={styles.metrics}>
          {metrics.map((metric) => (
            <div key={metric.label}>
              <span>{metric.label}</span>
              <strong className={styles[metric.tone]}>{metric.value}</strong>
              <em>{metric.sub}</em>
            </div>
          ))}
        </div>
        <div className={styles.trustLine}>
          {trustChecks.map((item) => (
            <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong><em>{item.sub}</em></div>
          ))}
        </div>
      </section>

      <ActionOutcomesPanel outcomes={actionOutcomes} />
      <ValidationPanel sectors={featuredSectors} rows={rows} />
      <MethodologyPanel modelNotes={modelNotes} />
    </div>
  )
}
