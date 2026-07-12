/**
 * HerdFlowPreview.jsx — Herd Flow 애니메이션 확인용 페이지.
 *
 * 실제 HERD 데이터와 무관하게 5단계 score를 고정 렌더링한다.
 */

import { useState } from 'react'
import HerdDots from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import { scoreColor } from '../../utils/herdStage'
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
  return scoreColor(score)
}

export default function HerdFlowPreview() {
  const [score, setScore] = useState(68)
  const [momentum, setMomentum] = useState(9)
  const [action, setAction] = useState(24)

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>Herd Flow Preview</div>
          <h1 className={styles.pageTitle}>Herd Flow 2.0</h1>
          <p className={styles.pageLead}>기존의 분산·밀집 언어는 유지하고, 실제 신호의 방향과 행동 강도를 움직임에 더했습니다.</p>
        </div>
      </div>

      <section className={styles.lab}>
        <div className={styles.labHead}><div><span>INTERACTIVE SIGNAL</span><h2>같은 HERD, 더 많은 정보</h2></div><strong style={{ color: stageColor(score) }}>{score}</strong></div>
        <div className={styles.compareGrid}>
          <div><div className={styles.compareLabel}>기존 · HERD만 반영</div><div className={styles.heroCanvas}><HerdDots score={score} fill dotCount={86} /></div></div>
          <div><div className={styles.compareLabel}>고도화 · 방향과 행동 반영</div><div className={styles.heroCanvas}><HerdDots score={score} momentum={momentum} actionRatio={action / 100} enhanced fill dotCount={86} /></div></div>
        </div>
        <div className={styles.controls}>
          <label><span>HERD <b>{score}</b></span><input type="range" min="0" max="100" value={score} onChange={(e) => setScore(Number(e.target.value))} /></label>
          <label><span>MOMENTUM <b>{momentum > 0 ? '+' : ''}{momentum}</b></span><input type="range" min="-20" max="20" value={momentum} onChange={(e) => setMomentum(Number(e.target.value))} /></label>
          <label><span>ACTION <b>{action}%</b></span><input type="range" min="0" max="60" value={action} onChange={(e) => setAction(Number(e.target.value))} /></label>
        </div>
      </section>

      <div className={styles.legacyHeader}>
        <span>BRAND LANGUAGE</span>
        <h2>다섯 단계의 성격은 그대로, 신호의 생동감만 강화</h2>
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
              <HerdDots score={stage.score} momentum={(stage.score - 50) / 3} actionRatio={stage.score >= 68 ? 0.22 : 0.08} enhanced fill dotCount={72} />
            </div>

            <SpectrumBar score={stage.score} height={3} />
            <p className={styles.note}>{stage.note}</p>
          </section>
        ))}
      </div>
    </div>
  )
}
