import styles from './Settings.module.css'

const STRATEGY_LABELS = {
  EXISTING_HOLDER: '기존 보유자',
  NEW_ENTRY: '신규 진입자',
  MONTHLY_DCA: '정기 적립식',
  TARGET_REBALANCE: '목표 비중 리밸런싱',
}

const RISK_LABELS = {
  CONSERVATIVE: '보수적',
  BALANCED: '균형',
  GROWTH: '성장형',
}

function NumberField({ label, unit, min, max, value, onChange }) {
  return (
    <label>
      <span>{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <small>{unit}</small>
    </label>
  )
}

export default function InvestorProfilePanel({ profile, status, onChange, onSubmit }) {
  return (
    <section className={styles.panel}>
      <details className={styles.disclosure}>
        <summary>
          <div>
            <span>저장된 투자 프로필</span>
            <strong>{profile
              ? `${STRATEGY_LABELS[profile.strategy]} · ${RISK_LABELS[profile.riskTolerance]} · 승인 시 상한 ${Math.round(Number(profile.maxActionRatio) * 100)}%`
              : '불러오는 중'}</strong>
          </div>
          <em>설정 변경</em>
        </summary>
        {profile ? (
          <form className={styles.profileForm} onSubmit={onSubmit}>
            <label>
              <span>투자 방식</span>
              <select value={profile.strategy} onChange={(event) => onChange('strategy', event.target.value)}>
                <option value="EXISTING_HOLDER">기존 보유자</option>
                <option value="NEW_ENTRY">신규 진입자</option>
                <option value="MONTHLY_DCA">정기 적립식</option>
                <option value="TARGET_REBALANCE">목표 비중 리밸런싱</option>
              </select>
            </label>
            <label>
              <span>위험 허용도</span>
              <select value={profile.riskTolerance} onChange={(event) => onChange('riskTolerance', event.target.value)}>
                <option value="CONSERVATIVE">보수적</option>
                <option value="BALANCED">균형</option>
                <option value="GROWTH">성장형</option>
              </select>
            </label>
            <NumberField label="투자 기간" unit="년" min="1" max="50" value={profile.timeHorizonYears} onChange={(value) => onChange('timeHorizonYears', value)} />
            <NumberField label="비상자금" unit="개월" min="0" max="60" value={profile.liquidityBufferMonths} onChange={(value) => onChange('liquidityBufferMonths', value)} />
            <NumberField label="향후 승인 시 1회 상한" unit="%" min="1" max="30" value={Math.round(Number(profile.maxActionRatio) * 100)} onChange={(value) => onChange('maxActionRatio', Number(value) / 100)} />
            <NumberField label="목표 주식 비중" unit="%" min="10" max="100" value={Math.round(Number(profile.targetEquityRatio) * 100)} onChange={(value) => onChange('targetEquityRatio', Number(value) / 100)} />
            <div className={styles.formActions}>
              <button type="submit">저장</button>
              {status && <em role="status">{status}</em>}
            </div>
          </form>
        ) : <p className={styles.inlineStatus}>{status}</p>}
      </details>
    </section>
  )
}
