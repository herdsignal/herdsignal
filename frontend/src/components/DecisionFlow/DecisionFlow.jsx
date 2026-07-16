import styles from './DecisionFlow.module.css'

function trendLabel(herd) {
  const reason = herd?.actionReasons?.find((item) => item.startsWith('장기 추세 품질'))
  if (reason) return reason.replace('장기 추세 품질 ', '품질 ')
  return herd?.indicators?.ma200Deviation >= 0 ? '추세 유지' : '추세 확인'
}

function weightLabel(currentWeight, targetWeight) {
  if (!Number.isFinite(currentWeight) || !Number.isFinite(targetWeight)) return '비중 미입력'
  const gap = currentWeight - targetWeight
  if (Math.abs(gap) < 3) return '목표 범위'
  return gap > 0 ? '목표 초과' : '목표 미달'
}

export default function DecisionFlow({ herd, currentWeight, targetWeight, compact = false }) {
  const stage = (herd?.herdStage ?? 'Calm').replace(/^Herd /, '')
  const action = herd?.actionLabel ?? herd?.signal ?? '관찰'
  const steps = [
    ['HERD', `${stage} ${Math.round(herd?.herdV4 ?? herd?.herdScore ?? 50)}`],
    ['추세', trendLabel(herd)],
    ['비중', weightLabel(currentWeight, targetWeight)],
    ['행동', action],
  ]

  return (
    <div className={`${styles.flow} ${compact ? styles.compact : ''}`} aria-label="행동 판단 흐름">
      {steps.map(([label, value], index) => (
        <div className={styles.stepWrap} key={label}>
          <div className={styles.step}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
          {index < steps.length - 1 && <i>→</i>}
        </div>
      ))}
    </div>
  )
}
