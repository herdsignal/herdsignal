import herdModelReport from '../../data/herdModelReport'
import styles from './HerdLab.module.css'

const { stages: STAGES, weights: WEIGHTS } = herdModelReport

const LEGACY_BASELINES = [
  {
    code: 'LEGACY_STATE_BASELINE',
    version: 'HERD v4',
    status: '기본 화면 제외',
    reason: 'State S1의 고정 관찰 계약으로 교체',
  },
  {
    code: 'LEGACY_RESEARCH_ACTION_BASELINE',
    version: 'HERD v6.1',
    status: '연구 비교 전용',
    reason: '운영 방향 증거·blind holdout 미통과',
  },
]

function barWidth(value, scale = 1) {
  const parsed = Number(String(value).replace(/[+%,/년p]/g, ''))
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed * scale)) : 0
}

export function ValidationPanel({ sectors, rows }) {
  return (
    <section className={styles.panel}>
      <SectionHead eyebrow="검증 요약" title="대표 6개 섹터" meta={`섹터 중앙값 기준 · 전체 ${rows.length}종목`} />
      <div className={styles.sectorList}>
        {sectors.map((sector) => (
          <article key={sector.name}>
            <div><strong>{sector.name}</strong><span>{sector.representative} 외 {Math.max(0, sector.count - 1)}개</span></div>
            <dl>
              <div><dt>수익 보존</dt><dd>{sector.capture}</dd></div>
              <div><dt>MDD 개선</dt><dd className={styles.green}>{sector.mdd}</dd></div>
              <div><dt>통과</dt><dd>{sector.passed}/{sector.count}</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <details className={styles.tableDisclosure}>
        <summary>전체 {rows.length}종목 결과 보기</summary>
        <div className={styles.table}>
          <div className={`${styles.tr} ${styles.th}`}><span>종목</span><span>B&H</span><span>Action</span><span>보존율</span><span>MDD 개선</span><span>행동</span><span>판정</span></div>
          {rows.map((row) => (
            <div key={row.ticker} className={styles.tr}>
              <span><strong>{row.ticker}</strong><small>{row.sector}</small></span><span>{row.buyHold}</span><span>{row.action}</span>
              <span>{row.capture}<Bar className={styles.captureBar} width={barWidth(row.capture)} /></span>
              <span className={styles.green}>{row.mdd}<Bar className={styles.mddBar} width={barWidth(row.mdd, 8)} /></span>
              <span>{row.actions}</span><span><em className={styles[row.tone]}>{row.verdict}</em></span>
            </div>
          ))}
        </div>
      </details>
    </section>
  )
}

export function ActionOutcomesPanel({ outcomes }) {
  return (
    <section className={styles.panel}>
      <SectionHead eyebrow="행동 사후 평가" title="행동 후 실제 결과" meta="완료된 관측만 집계" />
      <div className={styles.outcomeGrid}>
        {outcomes.map((outcome) => (
          <article key={outcome.horizon}>
            <span>{outcome.horizon}</span>
            <strong>{outcome.hitRate}</strong>
            <p>{outcome.samples}회 · 미행동 대비 {outcome.delta}</p>
            <em>평균 경로 낙폭 {outcome.drawdown}</em>
          </article>
        ))}
      </div>
    </section>
  )
}

export function LegacyBaselinesPanel() {
  return (
    <section className={styles.panel}>
      <SectionHead
        eyebrow="레거시 비교군"
        title="운영 기본 화면에서 분리"
        meta="계산·DB·기록 재현은 유지"
      />
      <div className={styles.legacyGrid}>
        {LEGACY_BASELINES.map((baseline) => (
          <article key={baseline.code}>
            <span>{baseline.code}</span>
            <strong>{baseline.version}</strong>
            <em>{baseline.status}</em>
            <p>{baseline.reason}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

function Bar({ className, width }) {
  return <i className={className}><b style={{ width: `${width}%` }} /></i>
}

export function MethodologyPanel({ modelNotes }) {
  return (
    <details className={`${styles.panel} ${styles.methodology}`}>
      <summary><div><span>모델 상세</span><strong>행동 비율·점수 구성·검증 주의사항</strong></div><em>자세히 보기</em></summary>
      <div className={styles.methodGrid}>
        <div><h3>구간별 기본 행동</h3><div className={styles.stageGrid}>{STAGES.map((item) => (
          <div key={item.stage}><i className={styles[item.tone]} /><strong>{item.stage}</strong><span>{item.range}</span><em>{item.action}</em><b>{item.ratio}</b></div>
        ))}</div></div>
        <div><h3>LEGACY_STATE_BASELINE · v4</h3><div className={styles.weightList}>{WEIGHTS.map((weight) => (
          <div key={weight.label}><span>{weight.label}</span><i><b style={{ width: `${weight.value * 3}%` }} /></i><strong>{weight.value}%</strong></div>
        ))}</div></div>
      </div>
      <ul className={styles.modelNotes}>{modelNotes.map((note) => <li key={note}>{note}</li>)}</ul>
    </details>
  )
}

function SectionHead({ eyebrow, title, meta }) {
  return <div className={styles.sectionHead}><div><span>{eyebrow}</span><strong>{title}</strong></div><p>{meta}</p></div>
}
