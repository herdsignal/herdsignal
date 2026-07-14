/**
 * HerdLab.jsx — HERD Index 검증 데이터 보드 (/herd-lab)
 */

import { useEffect, useState } from 'react'
import { getModelValidationReport } from '../../api/herdApi'
import herdModelReport from '../../data/herdModelReport'
import styles from './HerdLab.module.css'
import { presentValidationReport } from './herdModelPresentation'

const {
  model: MODEL_BASE,
  stages: STAGES,
  weights: WEIGHTS,
} = herdModelReport

function pctWidth(value) {
  const n = Number(String(value).replace(/[+%,/년p]/g, ''))
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n))
}

function mddWidth(value) {
  const n = Number(String(value).replace(/[+%p]/g, ''))
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n * 8))
}

export default function HerdLab() {
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getModelValidationReport()
      .then(({ data }) => {
        if (active) setReport(presentValidationReport(data.data))
      })
      .catch((requestError) => {
        if (active) setError(requestError.response?.data?.message || '검증 리포트를 불러오지 못했습니다.')
      })
    return () => { active = false }
  }, [])

  if (error) {
    return (
      <div className={styles.page}>
        <section className={styles.card} role="alert">
          <div className={styles.cardHead}><span>HERD LAB</span><strong>리포트 조회 실패</strong></div>
          <p>{error}</p>
        </section>
      </div>
    )
  }

  if (!report) {
    return <div className={styles.page}><p>최신 검증 리포트를 불러오는 중입니다.</p></div>
  }

  const { model, metrics, trustChecks, modelNotes, rows } = report

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span>HERD LAB</span>
          <h1>{model.version}</h1>
        </div>
        <p>{MODEL_BASE.name} · {model.generatedAt} 갱신</p>
      </header>

      <section className={styles.labHero}>
        <div className={styles.labHeroMain}>
          <span>Current Model</span>
          <strong>{model.version}</strong>
          <em>{MODEL_BASE.name} · 검증 기간 {model.period}</em>
          <small>{MODEL_BASE.base} · {MODEL_BASE.status}</small>
        </div>
        <div className={styles.labHeroMetrics}>
          {metrics.map((metric) => (
            <div key={metric.label}>
              <span>{metric.label}</span>
              <strong className={styles[metric.tone]}>{metric.value}</strong>
              <em>{metric.sub}</em>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.trustStrip}>
        {trustChecks.map((item) => (
          <div key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <em>{item.sub}</em>
          </div>
        ))}
      </section>

      <section className={styles.card}>
        <div className={styles.cardHead}>
          <span>검증 결과</span>
          <strong>Buy & Hold vs Action Layer</strong>
        </div>
        <div className={styles.table}>
          <div className={`${styles.tr} ${styles.th}`}>
            <span>종목</span>
            <span>B&H</span>
            <span>Action</span>
            <span>보존율</span>
            <span>MDD 개선</span>
            <span>행동</span>
            <span>판정</span>
          </div>
          {rows.map((row) => (
            <div key={row.ticker} className={styles.tr}>
              <span><strong>{row.ticker}</strong></span>
              <span>{row.buyHold}</span>
              <span>{row.action}</span>
              <span>
                {row.capture}
                <i className={styles.captureBar}><b style={{ width: `${pctWidth(row.capture)}%` }} /></i>
              </span>
              <span className={styles.green}>
                {row.mdd}
                <i className={styles.mddBar}><b style={{ width: `${mddWidth(row.mdd)}%` }} /></i>
              </span>
              <span>{row.actions}</span>
              <span><em className={styles[row.tone]}>{row.verdict}</em></span>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.gridTwo}>
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span>행동 매트릭스</span>
            <strong>구간별 행동 비율</strong>
          </div>
          <div className={styles.stageGrid}>
            {STAGES.map((item) => (
              <div key={item.stage} className={styles.stageRow}>
                <span className={`${styles.dot} ${styles[item.tone]}`} />
                <strong>{item.stage}</strong>
                <em>{item.range}</em>
                <span>{item.action}</span>
                <b>{item.ratio}</b>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span>점수 구성</span>
            <strong>HERD_v4 점수 구성</strong>
          </div>
          <div className={styles.weightList}>
            {WEIGHTS.map((weight) => (
              <div key={weight.label} className={styles.weightRow}>
                <span>{weight.label}</span>
                <div><i style={{ width: `${weight.value * 3}%` }} /></div>
                <strong>{weight.value}%</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.cardHead}>
          <span>모델 상태</span>
          <strong>검증 수치와 운영 보정 분리</strong>
        </div>
        <div className={styles.modelNotes}>
          {modelNotes.map((note, index) => (
            <div key={note}>
              <span>{index + 1}</span>
              <strong>{note}</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
