import HerdDots from '../../components/HerdDots/HerdDots'
import SpectrumBar from '../../components/SpectrumBar/SpectrumBar'
import {
  fmtPct,
  fmtScoreDate,
  pctColor,
  scoreToColor,
  scoreToStage,
  signalStyle,
  stageColor,
  stageDesc,
} from './dashboardModel'
import styles from './Dashboard.module.css'

export default function DashboardMobile({
  spyData, spyScore, spyStage, spyMomentum, lastUpdated,
  d1AvgPoint, m1AvgPoint, y1AvgPoint,
  loading, error, portfolio, actionQueueCards,
  summary, displayAmount, cashBalance, currencyMode,
  assetPanelOpen, onCurrencyToggle, onToggleAssetPanel, onNavigate,
}) {
  return (
    <section className={styles.mobileDashboard} aria-label="모바일 대시보드">
      {!loading && !error && portfolio.length > 0 && (
        <MobileActionQueue cards={actionQueueCards} onNavigate={onNavigate} />
      )}
      <MobileMarketSignal
        spyData={spyData} spyScore={spyScore} spyStage={spyStage}
        spyMomentum={spyMomentum} lastUpdated={lastUpdated}
        points={[d1AvgPoint, m1AvgPoint, y1AvgPoint]}
      />
      {summary && (
        <MobileAssetSummary
          summary={summary} displayAmount={displayAmount} cashBalance={cashBalance}
          currencyMode={currencyMode} assetPanelOpen={assetPanelOpen}
          onCurrencyToggle={onCurrencyToggle} onToggleAssetPanel={onToggleAssetPanel}
        />
      )}
    </section>
  )
}

function MobileMarketSignal({ spyData, spyScore, spyStage, spyMomentum, lastUpdated, points }) {
  const labels = ['1일 평균', '1달 평균', '1년 평균']
  return (
    <article className={styles.mobileSignalCard}>
      <div className={styles.mobileSignalTop}>
        <div><span className={styles.mobileKicker}>Market Signal</span><strong className={styles.mobileSignalTitle}>S&amp;P 500 HERD</strong></div>
        <div className={styles.mobileSignalUpdate}>{spyData ? fmtScoreDate(spyData.scoreDate, lastUpdated) : '대기'}</div>
      </div>
      <div className={styles.mobileSignalMain}>
        <div className={styles.mobileSignalScore}>
          <strong style={{ color: stageColor(spyStage) }}>{spyData ? Math.round(spyScore) : '—'}</strong>
          <span style={{ color: stageColor(spyStage) }}>{spyStage.startsWith('Herd ') ? spyStage : `Herd ${spyStage}`}</span>
          <em>{stageDesc(spyStage)}</em>
        </div>
        <div className={styles.mobileSignalFlow}>
          <HerdDots score={spyScore} momentum={spyMomentum.delta ?? (spyScore - 50) / 3} actionRatio={spyData?.actionRatio ?? 0} enhanced fill dotCount={52} />
          <div className={styles.mobileSpectrum}><SpectrumBar score={spyScore} height={3} /></div>
        </div>
      </div>
      <div className={styles.mobileSignalStats}>
        {points.map((point, index) => (
          <div key={labels[index]}>
            <span>{labels[index]}</span>
            <strong style={{ color: scoreToColor(point?.score) }}>{point?.score != null ? Math.round(point.score) : '—'}</strong>
            <em>{scoreToStage(point?.score) ?? '—'}</em>
          </div>
        ))}
      </div>
    </article>
  )
}

function MobileActionQueue({ cards, onNavigate }) {
  return (
    <article className={styles.mobileActionPanel}>
      <div className={styles.mobileSectionHead}>
        <div><span className={styles.mobileKicker}>Action Queue</span><strong>{cards.length > 0 ? `${cards.length}개 관찰 후보` : '강한 행동 신호 없음'}</strong></div>
        <button type="button" onClick={() => onNavigate('/watchlist')}>대기열</button>
      </div>
      <div className={styles.mobileActionList}>
        {cards.length > 0 ? cards.map((card) => {
          const actionColor = card.action.muted ? 'var(--calm)' : signalStyle(card.herd.signal).color
          const actionTone = card.action.code.startsWith('SELL') || card.action.code.startsWith('REDUCE')
            ? styles.mobileActionSell
            : card.action.code.startsWith('ADD') || card.action.code.startsWith('BUY')
              ? styles.mobileActionBuy : styles.mobileActionHold
          return (
            <button key={card.ticker} type="button" className={`${styles.mobileActionItem} ${actionTone}`} onClick={() => onNavigate(`/stock/${card.ticker}`)}>
              <div className={styles.mobileActionCode} style={{ color: actionColor }}>{card.action.code}</div>
              <div className={styles.mobileActionBody}><strong>{card.ticker}</strong><span>{card.stage} · HERD {card.score}</span><em>{card.action.text}</em></div>
              <div className={styles.mobileActionMeta}><span>{card.row.currentWeight.toFixed(1)}%</span><em>목표 {card.row.targetWeight.toFixed(1)}%</em></div>
            </button>
          )
        }) : <div className={styles.mobileActionEmpty}>장기투자 지표라 매일 행동 신호가 나오지 않는 것이 정상입니다.</div>}
      </div>
    </article>
  )
}

function MobileAssetSummary({ summary, displayAmount, cashBalance, currencyMode, assetPanelOpen, onCurrencyToggle, onToggleAssetPanel }) {
  return (
    <article className={styles.mobileAssetSummary}>
      <div className={styles.mobileAssetTop}>
        <div><span className={styles.mobileKicker}>Portfolio</span><strong>{displayAmount(summary.total_value)}</strong><em style={{ color: pctColor(summary.total_return_pct) }}>{fmtPct(summary.total_return_pct)}</em></div>
        <div className={styles.currencyToggle}>
          {['KRW', 'USD'].map((currency) => <button key={currency} className={`${styles.currencyBtn} ${currencyMode === currency ? styles.currencyBtnActive : ''}`} onClick={() => onCurrencyToggle(currency)}>{currency === 'KRW' ? '₩' : '$'}</button>)}
        </div>
      </div>
      <div className={styles.mobileAssetGrid}>
        <div><span>주식</span><strong>{displayAmount(summary.invested_value ?? summary.total_value)}</strong></div>
        <div><span>현금</span><strong>{displayAmount(summary.cash_balance ?? cashBalance)}</strong></div>
        <div><span>오늘</span><strong style={{ color: pctColor(summary.daily_change_pct) }}>{fmtPct(summary.daily_change_pct)}</strong></div>
      </div>
      <button type="button" className={styles.mobileAssetButton} onClick={onToggleAssetPanel}>{assetPanelOpen ? '자산 히스토리 닫기' : '자산 히스토리 보기'}</button>
    </article>
  )
}
