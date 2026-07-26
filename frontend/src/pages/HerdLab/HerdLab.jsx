/**
 * HerdLab.jsx — HERD Index 검증 데이터 보드 (/herd-lab)
 */

import { useEffect, useState } from 'react'
import { getModelValidationReport, getShadowModelStatus } from '../../api/herdApi'
import herdModelReport from '../../data/herdModelReport'
import styles from './HerdLab.module.css'
import { presentValidationReport } from './herdModelPresentation'
import { presentShadowStatus } from './shadowModelPresentation'
import {
  ActionOutcomesPanel,
  LegacyBaselinesPanel,
  MethodologyPanel,
  ValidationPanel,
} from './HerdLabSections'

const { model: MODEL_BASE } = herdModelReport

export default function HerdLab() {
  const [report, setReport] = useState(null)
  const [shadow, setShadow] = useState(() => presentShadowStatus(null))
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    Promise.allSettled([getModelValidationReport(), getShadowModelStatus()])
      .then(([validationResult, shadowResult]) => {
        if (!active) return
        if (validationResult.status === 'fulfilled') {
          setReport(presentValidationReport(validationResult.value.data.data))
          setError('')
        } else {
          setError(
            validationResult.reason?.response?.data?.message
              || '과거 검증 리포트를 불러오지 못했습니다.',
          )
        }
        if (shadowResult.status === 'fulfilled') {
          setShadow(presentShadowStatus(shadowResult.value.data.data))
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  const model = report?.model

  return (
    <div className={styles.page}>
      <section className={styles.currentScope}>
        <header>
          <span>CURRENT OPERATING SCOPE</span>
          <h1>HERD 연구실</h1>
          <p>State S1 관찰 운영 · 행동 모델 미채택</p>
          <div className={`${styles.shadowStatus} ${styles[shadow.tone]}`}>
            <i />
            <span>{shadow.label}</span>
            {shadow.candidate && <strong>{shadow.candidate}</strong>}
          </div>
        </header>
        <div className={styles.scopeGrid}>
          <ScopeItem label="운영 지수" value="State S1" sub="시장·종목 상태" tone="blue" />
          <ScopeItem label="매수·익절 모델" value="비활성" sub="채택 후보 없음" tone="slate" />
          <ScopeItem
            label="Shadow 후보"
            value={shadow.candidate ?? '없음'}
            sub={shadow.candidate ? '병렬 관측 중' : '검증 통과 대기'}
            tone={shadow.candidate ? 'blue' : 'slate'}
          />
          <ScopeItem
            label="최신 연구 기록"
            value={model?.generatedAt ?? (loading ? '확인 중' : '없음')}
            sub="과거 모델 보고서"
            tone="slate"
          />
        </div>
      </section>

      {report
        ? <ResearchArchive report={report} />
        : (
          <section className={styles.panel} aria-live="polite">
            <p className={styles.inlineStatus}>
              {loading ? '과거 검증 리포트 확인 중' : error}
            </p>
          </section>
          )}
    </div>
  )
}

function ScopeItem({ label, value, sub, tone }) {
  return (
    <div>
      <span>{label}</span>
      <strong className={styles[tone]}>{value}</strong>
      <em>{sub}</em>
    </div>
  )
}

function ResearchArchive({ report }) {
  const {
    model,
    metrics,
    trustChecks,
    modelNotes,
    rows,
    featuredSectors,
    actionOutcomes,
  } = report

  return (
    <details className={`${styles.panel} ${styles.archive}`}>
      <summary>
        <div>
          <span>HISTORICAL RESEARCH</span>
          <strong>v4 · v6.1 검증 기록</strong>
        </div>
        <em>운영 연결 없음</em>
      </summary>
      <div className={styles.archiveBody}>
        <section className={styles.archiveOverview}>
          <header>
            <span>LEGACY REPORT</span>
            <strong>{model.version} · {MODEL_BASE.name}</strong>
            <em>{model.generatedAt}</em>
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
        <LegacyBaselinesPanel />
        <ActionOutcomesPanel outcomes={actionOutcomes} />
        <ValidationPanel sectors={featuredSectors} rows={rows} />
        <MethodologyPanel modelNotes={modelNotes} />
      </div>
    </details>
  )
}
