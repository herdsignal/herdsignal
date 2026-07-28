/**
 * HerdLab.jsx — HERD Index 검증 데이터 보드 (/herd-lab)
 */

import { useEffect, useState } from 'react'
import {
  getModelValidationReport,
  getProspectiveEvidenceStatus,
  getShadowModelStatus,
  getVNextModelStatus,
} from '../../api/herdApi'
import herdModelReport from '../../data/herdModelReport'
import styles from './HerdLab.module.css'
import { presentValidationReport } from './herdModelPresentation'
import { presentShadowStatus } from './shadowModelPresentation'
import { presentVNextStatus } from './vNextModelPresentation'
import { presentProspectiveEvidence } from './prospectiveEvidencePresentation'
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
  const [vNext, setVNext] = useState(() => presentVNextStatus(null))
  const [prospective, setProspective] = useState(() => presentProspectiveEvidence(null))
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    Promise.allSettled([
      getModelValidationReport(),
      getShadowModelStatus(),
      getVNextModelStatus(),
      getProspectiveEvidenceStatus(),
    ])
      .then(([validationResult, shadowResult, vNextResult, prospectiveResult]) => {
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
        if (vNextResult.status === 'fulfilled') {
          setVNext(presentVNextStatus(vNextResult.value.data.data))
        }
        if (prospectiveResult.status === 'fulfilled') {
          setProspective(presentProspectiveEvidence(prospectiveResult.value.data.data))
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

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
          <ScopeItem label="운영 관찰" value={vNext.observationLabel} sub="시장·종목 상태" tone="blue" />
          <ScopeItem label="매수·익절 후보" value={vNext.actionLabel} sub="운영 연결 없음" tone="slate" />
          <ScopeItem label="운영 행동 비율" value={vNext.actionRatioLabel} sub="기본 행동 HOLD" tone="slate" />
          <ScopeItem label="Blind holdout" value={vNext.holdoutLabel} sub="승격 전까지 잠금" tone="slate" />
          <ScopeItem
            label="Shadow 후보"
            value={shadow.candidate ?? '없음'}
            sub={shadow.candidate ? '병렬 관측 중' : '검증 통과 대기'}
            tone={shadow.candidate ? 'blue' : 'slate'}
          />
          <div className={styles.gateSummary}>
            <span>현재 승격 차단</span>
            <div>
              {vNext.blockers.map((blocker) => <em key={blocker}>{blocker}</em>)}
            </div>
          </div>
        </div>
      </section>

      <section className={styles.prospectiveScope}>
        <header>
          <div>
            <span>PROSPECTIVE OBSERVATION</span>
            <strong>전향 관찰 원장</strong>
          </div>
          <em>{prospective.period}</em>
        </header>
        <div>
          <ScopeItem label="감사 상태" value={prospective.statusLabel} sub="해시·행동 차단 계약" tone={prospective.available ? 'blue' : 'slate'} />
          <ScopeItem label="관찰일" value={prospective.archives} sub="덮어쓰기 금지" tone="slate" />
          <ScopeItem label="관찰 레코드" value={prospective.records} sub="당시 추적 범위 고정" tone="slate" />
          <ScopeItem label="성숙 결과" value={prospective.matured} sub={`대기 ${prospective.pending}`} tone="slate" />
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
