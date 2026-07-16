import herdModelReport from '../../data/herdModelReport'
import styles from './HerdLab.module.css'

const { stages: STAGES, weights: WEIGHTS } = herdModelReport

const ACTION_GUIDES = [
  ['BUY', 'buy', 'Flee · Scatter', '추세 유지', '분할 매수'],
  ['HOLD', 'hold', 'Calm · Healthy', '추세 지속', '비중 유지'],
  ['REDUCE', 'reduce', 'Drift · Rush', '과열 둔화', '분할 익절'],
]

const STRATEGY_LABELS = {
  EXISTING_HOLDER: '기존 보유자', NEW_ENTRY: '신규 진입자',
  MONTHLY_DCA: '정기 적립식', TARGET_REBALANCE: '목표 비중 리밸런싱',
}

const RISK_LABELS = { CONSERVATIVE: '보수적', BALANCED: '균형', GROWTH: '성장형' }

function barWidth(value, scale = 1) {
  const parsed = Number(String(value).replace(/[+%,/년p]/g, ''))
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed * scale)) : 0
}

export function InvestorProfilePanel({ profile, status, onChange, onSubmit }) {
  return (
    <section className={styles.panel}>
      <details className={styles.disclosure}>
        <summary>
          <div>
            <span>내 투자 기준</span>
            <strong>{profile
              ? `${STRATEGY_LABELS[profile.strategy]} · ${RISK_LABELS[profile.riskTolerance]} · 1회 최대 ${Math.round(Number(profile.maxActionRatio) * 100)}%`
              : '투자 기준을 불러오는 중입니다.'}</strong>
          </div>
          <em>설정 변경</em>
        </summary>
        {profile ? (
          <form className={styles.profileForm} onSubmit={onSubmit}>
            <label><span>투자 방식</span><select value={profile.strategy} onChange={(event) => onChange('strategy', event.target.value)}>
              <option value="EXISTING_HOLDER">기존 보유자</option><option value="NEW_ENTRY">신규 진입자</option>
              <option value="MONTHLY_DCA">정기 적립식</option><option value="TARGET_REBALANCE">목표 비중 리밸런싱</option>
            </select></label>
            <label><span>위험 허용도</span><select value={profile.riskTolerance} onChange={(event) => onChange('riskTolerance', event.target.value)}>
              <option value="CONSERVATIVE">보수적</option><option value="BALANCED">균형</option><option value="GROWTH">성장형</option>
            </select></label>
            <NumberField label="투자 기간" unit="년" min="1" max="50" value={profile.timeHorizonYears} onChange={(value) => onChange('timeHorizonYears', value)} />
            <NumberField label="비상자금" unit="개월" min="0" max="60" value={profile.liquidityBufferMonths} onChange={(value) => onChange('liquidityBufferMonths', value)} />
            <NumberField label="1회 최대 행동" unit="%" min="1" max="30" value={Math.round(Number(profile.maxActionRatio) * 100)} onChange={(value) => onChange('maxActionRatio', Number(value) / 100)} />
            <NumberField label="목표 주식 비중" unit="%" min="10" max="100" value={Math.round(Number(profile.targetEquityRatio) * 100)} onChange={(value) => onChange('targetEquityRatio', Number(value) / 100)} />
            <div className={styles.formActions}><button type="submit">저장</button>{status && <em role="status">{status}</em>}</div>
          </form>
        ) : <p className={styles.inlineStatus}>{status}</p>}
      </details>
    </section>
  )
}

function NumberField({ label, unit, min, max, value, onChange }) {
  return (
    <label><span>{label}</span><input type="number" min={min} max={max} value={value} onChange={(event) => onChange(event.target.value)} /><small>{unit}</small></label>
  )
}

export function ActionGuide() {
  return (
    <section className={styles.panel}>
      <SectionHead eyebrow="행동 기준" title="HERD와 추세를 함께 확인" meta="점수만으로 행동하지 않음" />
      <div className={styles.decisionRail} aria-label="행동 판단 순서">
        <span>투자 가능</span><i>→</i><span>HERD</span><i>→</i><span>추세</span><i>→</i><span>비중</span><i>→</i><strong>행동</strong>
      </div>
      <div className={styles.actionGuide}>
        {ACTION_GUIDES.map(([code, tone, herd, confirmation, action]) => (
          <article key={code} className={styles[tone]}>
            <span>{code}</span>
            <div className={styles.actionFormula}>
              <strong>{herd}</strong><i>+</i><em>{confirmation}</em><b>→</b>
            </div>
            <p>{action}</p>
          </article>
        ))}
      </div>
    </section>
  )
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
        <div><h3>HERD_v4 점수 구성</h3><div className={styles.weightList}>{WEIGHTS.map((weight) => (
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
