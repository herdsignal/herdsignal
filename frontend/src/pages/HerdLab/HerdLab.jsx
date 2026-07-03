/**
 * HerdLab.jsx — HERD Index 검증 데이터 보드 (/herd-lab)
 */

import styles from './HerdLab.module.css'
import herdModelReport from '../../data/herdModelReport'

const {
  model: MODEL,
  metrics: METRICS,
  rows: TEST_ROWS,
  stages: STAGES,
  weights: WEIGHTS,
  checks: CHECKS,
} = herdModelReport

export default function HerdLab() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span>HERD LAB</span>
          <h1>{MODEL.version}</h1>
        </div>
        <p>{MODEL.name} · {MODEL.release} · 내부 백테스트 기준</p>
      </header>

      <section className={styles.modelStrip}>
        <div>
          <span>Model</span>
          <strong>{MODEL.version}</strong>
        </div>
        <div>
          <span>Layer</span>
          <strong>{MODEL.name}</strong>
        </div>
        <div>
          <span>Input</span>
          <strong>{MODEL.base}</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>{MODEL.status}</strong>
        </div>
      </section>

      <section className={styles.metricGrid}>
        {METRICS.map((metric) => (
          <div key={metric.label} className={styles.metricCard}>
            <span>{metric.label}</span>
            <strong className={styles[metric.tone]}>{metric.value}</strong>
            <em>{metric.sub}</em>
          </div>
        ))}
      </section>

      <section className={styles.card}>
        <div className={styles.cardHead}>
          <span>Backtest</span>
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
          </div>
          {TEST_ROWS.map((row) => (
            <div key={row.ticker} className={styles.tr}>
              <span><strong>{row.ticker}</strong></span>
              <span>{row.buyHold}</span>
              <span>{row.action}</span>
              <span>{row.capture}</span>
              <span className={styles.green}>{row.mdd}</span>
              <span>{row.actions}</span>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.gridTwo}>
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span>Action Matrix</span>
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
            <span>Formula</span>
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

      <section className={styles.checkGrid}>
        {CHECKS.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </section>
    </div>
  )
}
