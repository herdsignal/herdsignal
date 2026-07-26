import styles from './HerdLens.module.css'
import {
  clampHerdScore,
  createHerdLensDots,
  herdLensLabel,
  resolvePreviousScore,
} from './herdLensModel'
import {
  normalizeStage,
  stageFromScore,
  stageLabelFromScore,
} from '../../utils/herdStage'

const LENS_COLORS = {
  flee: 'var(--hs-flee)',
  scatter: 'var(--hs-scatter)',
  calm: 'var(--hs-calm)',
  drift: 'var(--hs-drift)',
  rush: 'var(--hs-rush)',
}

function classNames(...values) {
  return values.filter(Boolean).join(' ')
}

export default function HerdLens({
  score,
  stage,
  previousScore,
  delta,
  dotCount,
  compact = false,
  className,
}) {
  const normalizedScore = clampHerdScore(score)
  const resolvedStage = normalizeStage(stage)
    || stageFromScore(normalizedScore)
    || 'calm'
  const resolvedPrevious = resolvePreviousScore(
    normalizedScore,
    previousScore,
    delta,
  )
  const dots = createHerdLensDots(normalizedScore, dotCount)
  const unavailable = normalizedScore == null
  const currentPosition = unavailable ? 50 : normalizedScore

  return (
    <div
      className={classNames(
        styles.root,
        compact && styles.compact,
        unavailable && styles.unavailable,
        resolvedPrevious == null && styles.withoutHistory,
        styles[resolvedStage],
        className,
      )}
      style={{
        '--lens-color': LENS_COLORS[resolvedStage] || LENS_COLORS.calm,
        '--current-score': `${currentPosition}%`,
        '--previous-score': `${resolvedPrevious ?? currentPosition}%`,
      }}
      role="img"
      aria-label={herdLensLabel({
        score: normalizedScore,
        stage: resolvedStage,
        previousScore: resolvedPrevious,
      })}
    >
      <span className={styles.lens} aria-hidden="true">
        {dots.map((dot, index) => (
          <i
            className={styles.dot}
            key={index}
            style={{
              '--dot-x': `${dot.x}%`,
              '--dot-y': `${dot.y}%`,
              '--dot-size': `${dot.size}px`,
              '--dot-opacity': dot.opacity,
              '--dot-drift-x': `${((dot.x - 50) * 0.09).toFixed(2)}px`,
              '--dot-drift-y': `${((index % 3) - 1) * 2.2}px`,
              '--dot-duration': `${(2.8 + (index % 5) * 0.32).toFixed(2)}s`,
              '--dot-delay': `${(-index * 0.13).toFixed(2)}s`,
            }}
          />
        ))}
      </span>
      <span className={styles.reading} aria-hidden="true">
        <b className={styles.score}>
          {unavailable ? '—' : Math.round(normalizedScore)}
        </b>
        <small className={styles.stage}>
          {unavailable ? 'Unavailable' : stageLabelFromScore(normalizedScore)}
        </small>
      </span>
      <span className={styles.motion} aria-hidden="true">
        <i className={styles.previous} />
        <i className={styles.current} />
      </span>
    </div>
  )
}
