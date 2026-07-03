/**
 * HerdFlowPreview.jsx — Herd Flow 애니메이션 확인용 페이지.
 *
 * 실제 HERD 데이터와 무관하게 5단계 score를 고정 렌더링한다.
 */

import HerdDots from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import styles from './HerdFlowPreview.module.css'

const STAGES = [
  {
    score: 8,
    name: 'Flee',
    desc: '군중 이탈',
    note: '화면 전체에 듬성듬성 분산',
  },
  {
    score: 28,
    name: 'Scatter',
    desc: '군중 흩어짐',
    note: '작은 군집들이 깨져 흩어짐',
  },
  {
    score: 50,
    name: 'Calm',
    desc: '군중 균형',
    note: '중앙에서 안정적으로 분포',
  },
  {
    score: 68,
    name: 'Drift',
    desc: '군중 쏠림',
    note: '오른쪽으로 느슨하게 기울어짐',
  },
  {
    score: 88,
    name: 'Rush',
    desc: '군중 밀집',
    note: '오른쪽 좁은 영역에 촘촘히 모임',
  },
]

function stageColor(score) {
  if (score >= 75) return 'var(--rush)'
  if (score >= 60) return 'var(--drift)'
  if (score >= 40) return 'var(--calm)'
  if (score >= 15) return 'var(--scatter)'
  return 'var(--flee)'
}

export default function HerdFlowPreview() {
  return (
    <div>
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>Herd Flow Preview</div>
          <h1 className={styles.pageTitle}>군중 분포 애니메이션</h1>
        </div>
      </div>

      <div className={styles.previewGrid}>
        {STAGES.map((stage) => (
          <section key={stage.name} className={styles.previewCard}>
            <div className={styles.cardTop}>
              <div>
                <div className={styles.stageName} style={{ color: stageColor(stage.score) }}>
                  {stage.name}
                </div>
                <div className={styles.stageDesc}>{stage.desc}</div>
              </div>
              <div className={styles.score} style={{ color: stageColor(stage.score) }}>
                {stage.score}
              </div>
            </div>

            <div className={styles.canvasWrap}>
              <HerdDots score={stage.score} fill dotCount={72} />
            </div>

            <SpectrumBar score={stage.score} height={3} />
            <p className={styles.note}>{stage.note}</p>
          </section>
        ))}
      </div>
    </div>
  )
}
