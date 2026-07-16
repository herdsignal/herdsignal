import { pctColor, fmtPct, signalStyle } from './dashboardModel'
import DecisionFlow from '../../components/DecisionFlow/DecisionFlow'
import styles from './Dashboard.module.css'

export default function DashboardTodayBrief({
  cards,
  alerts,
  summary,
  displayAmount,
  onOpenStock,
}) {
  const buyCount = cards.filter((card) => /^(BUY|ADD)/.test(card.action.code)).length
  const reduceCount = cards.filter((card) => /^(SELL|REDUCE)/.test(card.action.code)).length
  const headline = cards.length === 0
    ? '오늘 새로 할 행동은 없습니다.'
    : `${cards.length}개 종목을 먼저 확인하세요.`

  return (
    <section className={styles.todayBrief}>
      <div className={styles.todayConclusion}>
        <span>오늘의 결론</span>
        <h2>{headline}</h2>
        <p>
          {cards.length === 0
            ? '포트폴리오 비중과 장기 추세가 현재 기준 안에 있습니다.'
            : `매수 관찰 ${buyCount}개 · 축소 관찰 ${reduceCount}개 · 실행 전 종목별 근거를 확인하세요.`}
        </p>
        {summary && (
          <div className={styles.todayPortfolio}>
            <strong>{displayAmount(summary.total_value)}</strong>
            <em style={{ color: pctColor(summary.daily_change_pct) }}>
              오늘 {fmtPct(summary.daily_change_pct)}
            </em>
          </div>
        )}
      </div>

      <div className={styles.todayPriority}>
        <header>
          <div><span>우선 확인</span><strong>{cards.length > 0 ? `상위 ${Math.min(cards.length, 3)}종목` : '대기 상태'}</strong></div>
          {alerts.length > 0 && <em>추가 알림 {alerts.length}개</em>}
        </header>
        <div className={styles.todayPriorityList}>
          {cards.slice(0, 3).map((card) => {
            const actionColor = card.action.muted
              ? 'var(--calm)'
              : signalStyle(card.herd.signal).color
            return (
              <button key={card.ticker} type="button" onClick={() => onOpenStock(card.ticker)}>
                <div>
                  <strong>{card.ticker}</strong>
                  <span>{card.stage} · HERD {card.score}</span>
                </div>
                <div>
                  <strong style={{ color: actionColor }}>{card.action.code}</strong>
                  <span>{card.action.text}</span>
                </div>
              </button>
            )
          })}
          {cards.length === 0 && (
            <div className={styles.todayEmpty}>
              <strong>관찰 유지</strong>
              <span>장기투자 지표는 행동하지 않는 날이 더 많습니다.</span>
            </div>
          )}
        </div>
        {cards[0] && (
          <div className={styles.todayDecisionFlow}>
            <DecisionFlow
              herd={cards[0].herd}
              currentWeight={cards[0].row.currentWeight}
              targetWeight={cards[0].row.targetWeight}
              compact
            />
          </div>
        )}
      </div>
    </section>
  )
}
