/**
 * SpectrumBar.jsx — Flee~Rush 스펙트럼 바 + 현재 위치 thumb
 *
 * 좌(파랑=Flee) → 우(레드=Rush) 그라데이션 바.
 * score% 위치에 흰 원형 thumb을 표시.
 * 래퍼런스: wireframes/wireframe-home-v4.html .mini-spectrum-track
 */

import styles from './SpectrumBar.module.css'

/** score 구간별 thumb 테두리 색상 반환 */
function getThumbColor(score) {
  if (score >= 75) return 'var(--rush)'
  if (score >= 60) return 'var(--drift)'
  if (score >= 40) return 'var(--calm)'
  if (score >= 15) return 'var(--scatter)'
  return 'var(--flee)'
}

/**
 * @param {number}  score       HERD 점수 (0~100)
 * @param {number}  height      바 두께 (px, default 3)
 * @param {boolean} showLabels  Flee / Rush 라벨 표시 여부
 */
export default function SpectrumBar({
  score      = 50,
  height     = 3,
  showLabels = false,
}) {
  const thumbColor = getThumbColor(score)

  return (
    <div className={styles.wrapper}>
      {/* 선택적 라벨 */}
      {showLabels && (
        <div className={styles.labels}>
          <span className={styles.label}>Flee</span>
          <span className={styles.label}>Rush</span>
        </div>
      )}

      {/* 그라데이션 트랙 */}
      <div className={styles.track} style={{ height }}>
        {/* score% 위치에 thumb */}
        <div
          className={styles.thumb}
          style={{
            left:        `${Math.max(0, Math.min(100, score))}%`,
            borderColor: thumbColor,
            /* thumb 높이는 바 두께보다 크게 (시각적 강조) */
            width:       Math.max(height * 2.5, 8),
            height:      Math.max(height * 2.5, 8),
          }}
        />
      </div>
    </div>
  )
}
