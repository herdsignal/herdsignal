import {
  normalizeStage,
  stageFromScore,
  stageLabelFromScore,
} from '../../utils/herdStage'
import {
  clampHerdScore,
  herdLensLabel,
} from '../HerdLens/herdLensModel'
import {
  createMarketFieldDots,
  MARKET_FIELD_DOT_COUNT,
} from './marketFieldModel'
import styles from './MarketField.module.css'

const FIELD_COLORS = {
  flee: 'var(--hs-flee)',
  scatter: 'var(--hs-scatter)',
  calm: 'var(--hs-calm)',
  drift: 'var(--hs-drift)',
  rush: 'var(--hs-rush)',
}

const STAGES = [
  { label: 'Flee', at: 7.5 },
  { label: 'Scatter', at: 27.5 },
  { label: 'Calm', at: 50 },
  { label: 'Drift', at: 67.5 },
  { label: 'Rush', at: 87.5 },
]

export default function MarketField({ score, stage }) {
  const normalizedScore = clampHerdScore(score)
  const resolvedStage = normalizeStage(stage)
    || stageFromScore(normalizedScore)
    || 'calm'
  const dots = createMarketFieldDots(normalizedScore, MARKET_FIELD_DOT_COUNT)
  const unavailable = normalizedScore == null
  const currentPosition = unavailable ? 50 : normalizedScore

  return (
    <section
      className={`${styles.field} ${unavailable ? styles.unavailable : ''}`}
      style={{
        '--field-color': FIELD_COLORS[resolvedStage] || FIELD_COLORS.calm,
        '--field-score': `${currentPosition}%`,
      }}
      role="img"
      aria-label={herdLensLabel({
        score: normalizedScore,
        stage: resolvedStage,
        previousScore: null,
      })}
    >
      <div className={styles.dots} aria-hidden="true">
        {dots.map((dot, index) => (
          <i
            key={index}
            style={{
              '--dot-x': `${dot.x}%`,
              '--dot-y': `${dot.y}%`,
              '--dot-size': `${dot.size}px`,
              '--dot-opacity': dot.opacity,
            }}
          />
        ))}
      </div>

      <div className={styles.reading} aria-hidden="true">
        <strong>{unavailable ? '—' : Math.round(normalizedScore)}</strong>
        <span>
          {unavailable ? 'Unavailable' : stageLabelFromScore(normalizedScore)}
        </span>
      </div>

      <div className={styles.spectrum} aria-hidden="true">
        <i className={styles.current} />
        {STAGES.map((item) => (
          <span key={item.label} style={{ '--stage-position': `${item.at}%` }}>
            {item.label}
          </span>
        ))}
      </div>
    </section>
  )
}

