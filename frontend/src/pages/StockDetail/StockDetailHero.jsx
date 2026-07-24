import HerdDots from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import styles from './StockDetail.module.css'
import { getTimingSignal } from './stockDetailModel'

export default function StockDetailHero({
  observation,
  herdScore,
  stageDisp,
  color,
  herdMomentum,
}) {
  return (
    <>
      <div className={styles.herdCard}>
        <div className={styles.herdScoreSide}>
          <div className={styles.herdEyebrow}>HERD State S1</div>
          <div className={styles.herdBigScore} style={{ color }}>{Math.round(herdScore)}</div>
          <div className={styles.herdBigStage} style={{ color }}>{stageDisp}</div>
          <div
            className={styles.timingSignal}
            style={{ color }}
          >
            {getTimingSignal(herdScore)}
          </div>
          <div className={styles.qualityReason}>
            {observation.transition} · {observation.freshnessStatus === 'STALE' ? '업데이트 필요' : observation.lastObservedSession}
          </div>
        </div>

        <div className={styles.herdAnimSide}>
          <HerdDots
            score={herdScore}
            momentum={herdMomentum.delta ?? (herdScore - 50) / 3}
            actionRatio={0}
            enhanced
            fill
            dotCount={55}
          />
          <div className={styles.herdAnimBottom}>
            <SpectrumBar score={herdScore} height={3} />
            <div className={styles.spectrumLabels}>
              <span>Flee 군중 이탈</span>
              <span>Scatter 군중 흩어짐</span>
              <span>Calm 군중 균형</span>
              <span>Drift 군중 쏠림</span>
              <span>Rush 군중 밀집</span>
            </div>
          </div>
        </div>
      </div>

    </>
  )
}
