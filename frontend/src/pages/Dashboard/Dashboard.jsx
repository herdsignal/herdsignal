/**
 * Dashboard.jsx — 포트폴리오 대시보드 (/)
 * 보유 종목별 HERD 점수 카드 목록.
 *
 * [임시] HerdDots + SpectrumBar 컴포넌트 동작 확인용 테스트 렌더 포함.
 *        다음 단계에서 getPortfolioHerd() API 연동 후 제거 예정.
 */

import styles from './Dashboard.module.css'
import HerdDots    from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'

/* 테스트용 샘플 데이터 */
const TEST_CASES = [
  { ticker: 'TSLA', score: 83, label: 'Rush — 오른쪽 몰림' },
  { ticker: 'IONQ', score: 21, label: 'Scatter — 왼쪽 흩어짐' },
]

export default function Dashboard() {
  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  return (
    <div>
      {/* 페이지 헤더 */}
      <div className={styles.header}>
        <div>
          <div className={styles.date}>{today}</div>
          <h1 className={styles.title}>포트폴리오</h1>
        </div>
        <button className={styles.btnPrimary}>종목 추가</button>
      </div>

      {/* ── [임시] 컴포넌트 테스트 섹션 ── */}
      <div className={styles.testSection}>
        <p className={styles.testLabel}>HerdDots + SpectrumBar 동작 확인</p>
        <div className={styles.testRow}>
          {TEST_CASES.map(({ ticker, score, label }) => (
            <div key={ticker} className={styles.testCard}>
              {/* 티커 + 점수 */}
              <div className={styles.testCardHeader}>
                <span className={styles.testTicker}>{ticker}</span>
                <span className={styles.testScore} style={{ color: getScoreColor(score) }}>
                  {score}
                </span>
              </div>
              <p className={styles.testCardLabel}>{label}</p>

              {/* HerdDots 애니메이션 */}
              <div className={styles.dotsWrap}>
                <HerdDots score={score} width={260} height={110} dotCount={22} />
              </div>

              {/* SpectrumBar (라벨 포함) */}
              <div className={styles.spectrumWrap}>
                <SpectrumBar score={score} height={4} showLabels />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/** 점수 구간 색상 (인라인 스타일용) */
function getScoreColor(score) {
  if (score >= 75) return 'var(--rush)'
  if (score >= 60) return 'var(--drift)'
  if (score >= 40) return 'var(--calm)'
  if (score >= 15) return 'var(--scatter)'
  return 'var(--flee)'
}
