/**
 * History.jsx — 포트폴리오 자산 기록 (/history)
 *
 * 구성:
 *   - 월/년 토글 버튼
 *   - recharts LineChart (총 평가금액 시계열)
 *   - getPortfolioHistory(period) 연동
 */

import { useMemo, useState } from 'react'
import HistoryChart from './HistoryChart'
import { buildHistoryView, fmtPct, fmtUSD, pctColor } from './historyModel'
import { usePortfolioHistory } from './usePortfolioHistory'
import styles from './History.module.css'

/* ── 컴포넌트 ─────────────────────────────── */

export default function History() {
  const [period,  setPeriod]  = useState('month')
  const { points, summary, loading, error, fetchData } = usePortfolioHistory(period)

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  const { latest, insight: historyInsight, yDomain } = useMemo(
    () => buildHistoryView(points),
    [points]
  )

  return (
    <div className={styles.page}>

      {/* ── 페이지 헤더 ── */}
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>자산 히스토리</h1>
        </div>
        {/* 기간 토글 */}
        <div className={styles.periodToggle}>
          <button
            className={`${styles.toggleBtn} ${period === 'month' ? styles.active : ''}`}
            onClick={() => setPeriod('month')}
          >
            1개월
          </button>
          <button
            className={`${styles.toggleBtn} ${period === 'year' ? styles.active : ''}`}
            onClick={() => setPeriod('year')}
          >
            1년
          </button>
        </div>
      </div>

      {/* ── 현재 평가금액 요약 ── */}
      {summary && (
        <div className={styles.metaRow}>
          <div className={styles.metaItem}>
            <div className={styles.metaLabel}>현재 평가금액</div>
            <div className={styles.metaValue}>{fmtUSD(summary.totalValue)}</div>
          </div>
          <div className={styles.metaDivider} />
          <div className={styles.metaItem}>
            <div className={styles.metaLabel}>총 수익률</div>
            <div
              className={styles.metaValue}
              style={{ color: pctColor(summary.totalReturnPct) }}
            >
              {fmtPct(summary.totalReturnPct)}
            </div>
          </div>
          <div className={styles.metaDivider} />
          <div className={styles.metaItem}>
            <div className={styles.metaLabel}>오늘 등락</div>
            <div
              className={styles.metaValue}
              style={{ color: pctColor(summary.dailyChangePct) }}
            >
              {fmtPct(summary.dailyChangePct)}
            </div>
          </div>
        </div>
      )}

      {historyInsight && (
        <div className={styles.insightGrid}>
          <div className={styles.insightCard}>
            <span>시작 대비</span>
            <strong style={{ color: pctColor(historyInsight.fromStart) }}>
              {fmtPct(historyInsight.fromStart)}
            </strong>
            <em>{historyInsight.first.date} 이후</em>
          </div>
          <div className={styles.insightCard}>
            <span>고점 대비</span>
            <strong style={{ color: pctColor(historyInsight.drawdown) }}>
              {fmtPct(historyInsight.drawdown)}
            </strong>
            <em>고점 {fmtUSD(historyInsight.peak.totalValue)}</em>
          </div>
          <div className={styles.insightCard}>
            <span>점검 포인트</span>
            <strong>
              {historyInsight.drawdown != null && historyInsight.drawdown < -8
                ? '리밸런싱 확인'
                : '큰 낙폭 없음'}
            </strong>
            <em>HERD 상태와 함께 확인</em>
          </div>
        </div>
      )}

      {/* ── 차트 카드 ── */}
      <div className={styles.chartCard}>
        <div className={styles.chartTitleRow}>
          <span className={styles.chartTitle}>총 평가금액</span>
          {latest && (
            <span className={styles.chartLatest}>{fmtUSD(latest.totalValue)}</span>
          )}
        </div>

        {loading && <div className={styles.stateBox}><span className={styles.stateText}>로딩 중…</span></div>}

        {!loading && error && (
          <div className={styles.stateBox}>
            <span className={styles.stateText}>{error}</span>
            <button className={styles.retryBtn} onClick={fetchData}>다시 시도</button>
          </div>
        )}

        {!loading && !error && points.length === 0 && (
          <div className={styles.stateBox}>
            <span className={styles.stateText}>아직 자산 기록이 없습니다.</span>
            <span className={styles.stateDesc}>
              Python 스케줄러가 매일 스냅샷을 저장합니다.
            </span>
          </div>
        )}

        {!loading && !error && points.length > 0 && (
          <HistoryChart
            points={points}
            totalCost={summary?.totalCost}
            yDomain={yDomain}
          />
        )}
      </div>

      {/* ── 데이터 포인트 목록 ── */}
      {!loading && points.length > 0 && (
        <div className={styles.pointsCard}>
          <div className={styles.pointsHeader}>
            <div className={styles.pointsTh}>날짜</div>
            <div className={`${styles.pointsTh} ${styles.thRight}`}>평가금액</div>
            <div className={`${styles.pointsTh} ${styles.thRight}`}>총 수익률</div>
          </div>
          {[...points].reverse().map((p) => (
            <div key={p.date} className={styles.pointsRow}>
              <div className={styles.pointsDate}>
                {new Date(p.date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
              </div>
              <div className={`${styles.pointsValue} ${styles.thRight}`}>
                {fmtUSD(p.totalValue)}
              </div>
              <div className={`${styles.thRight}`} style={{ color: pctColor(p.totalReturnPct) }}>
                {fmtPct(p.totalReturnPct)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
