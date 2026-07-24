import DecisionFlow from '../../components/DecisionFlow/DecisionFlow'
import HerdDots from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import { qualityReasonText, qualityWarningText, shouldShowQuality } from '../../utils/dataQuality'
import { formatSignalAgeLabel, formatSignalDurationDetail } from '../../utils/signalDuration'
import styles from './StockDetail.module.css'
import {
  formatActionBasis,
  formatActionMeta,
  formatActionRatio,
  getTimingSignal,
} from './stockDetailModel'

export default function StockDetailHero({
  herdData,
  observation,
  herdScore,
  stageDisp,
  color,
  sigStyle,
  qualityToneColor,
  actionColor,
  decision,
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
            style={{ background: sigStyle.bg, color: sigStyle.color }}
          >
            {getTimingSignal(herdScore)}
          </div>
          <div className={styles.qualityReason}>
            {observation.transition} · {observation.freshnessStatus === 'STALE' ? '업데이트 필요' : observation.lastObservedSession}
          </div>
          {shouldShowQuality(herdData) && (
            <>
              <div
                className={styles.qualityPill}
                style={{ color: qualityToneColor, borderColor: qualityToneColor }}
                title={qualityReasonText(herdData)}
              >
                {qualityWarningText(herdData, { pointSuffix: true })}
              </div>
              <div className={styles.qualityReason}>{qualityReasonText(herdData)}</div>
            </>
          )}
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

      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <div className={styles.cardTitle}>Action Layer</div>
          <div className={styles.cardMeta}>{formatActionMeta(herdData)}</div>
        </div>
        <div className={styles.cardBody}>
          {herdData.actionModelStatus === 'RESEARCH_VALIDATION' && (
            <div className={styles.actionWarningList} role="status">
              <span>{herdData.actionDisclaimer ?? '연구 검증 중인 행동 보조 정보입니다.'}</span>
            </div>
          )}
          <div className={styles.decisionHero}>
            <div>
              <div className={styles.decisionLabel}>타이밍 액션</div>
              <div className={styles.decisionTitle}>
                {herdData.actionLabel ?? decision.title}
              </div>
              <div className={styles.decisionSubtitle}>
                {herdData.actionRegimeLabel ?? decision.subtitle}
              </div>
              <div className={styles.decisionBasis}>{formatActionBasis(herdData)}</div>
              {formatSignalDurationDetail(herdData) && (
                <div className={styles.decisionBasis}>{formatSignalAgeLabel(herdData)}</div>
              )}
              <div className={`${styles.decisionMomentum} ${styles[`decisionMomentum_${herdMomentum.tone}`] || ''}`}>
                <span>{herdMomentum.label}</span>
                <strong>{herdMomentum.detail}</strong>
              </div>
            </div>
            <div className={styles.decisionPill} style={{ color: actionColor, borderColor: actionColor }}>
              {formatActionRatio(herdData.actionRatio)}
            </div>
          </div>
          <DecisionFlow herd={herdData} />
          <div className={styles.decisionList}>
            {(herdData.actionReasons?.length ? herdData.actionReasons : decision.notes)
              .slice(0, 2)
              .map((note) => (
                <div key={note} className={styles.decisionItem}>{note}</div>
              ))}
          </div>
          {Array.isArray(herdData.actionWarnings) && herdData.actionWarnings.length > 0 && (
            <div className={styles.actionWarningList}>
              {herdData.actionWarnings.slice(0, 1).map((warning) => (
                <span key={warning}>{warning}</span>
              ))}
            </div>
          )}
          {herdData.oosValidationSummary && (
            <div className={styles.decisionBasis}>{herdData.oosValidationSummary}</div>
          )}
        </div>
      </div>
    </>
  )
}
