import StockAvatar from '../../components/StockAvatar/StockAvatar'
import { qualityColor, qualityReasonText, qualityWarningText, shouldShowQuality } from '../../utils/dataQuality'
import { formatSignalAgeLabel } from '../../utils/signalDuration'
import {
  PORTFOLIO_SORT_OPTIONS,
  badgeStyle,
  buildPositionAction,
  fmtPct,
  fmtShares,
  fmtWeightGap,
  pctColor,
  signalStyle,
  stageColor,
} from './dashboardModel'
import styles from './Dashboard.module.css'

export default function DashboardHoldings({
  portfolio,
  sortedPortfolio,
  rows,
  herdMap,
  priceMap,
  portfolioSort,
  editMode,
  deletingTicker,
  targetWeights,
  displayAmount,
  displayPnl,
  onSortChange,
  onDelete,
  onOpenStock,
  onEditHolding,
  onTargetWeightChange,
}) {
  if (portfolio.length === 0) return null

  return (
    <>
      <div className={styles.sectionRow}>
        <div className={styles.sectionTitle}>보유 종목 · {portfolio.length}</div>
        <div className={styles.sortTabs} aria-label="보유 종목 정렬">
          {PORTFOLIO_SORT_OPTIONS.map((option) => (
            <button
              key={option.value}
              className={`${styles.sortTab} ${portfolioSort === option.value ? styles.sortTabActive : ''}`}
              onClick={() => onSortChange(option.value)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.holdingsTable}>
        <div className={styles.holdingsHeader}>
          <span>종목</span><span>보유 비중</span><span>평가금액</span>
          <span>수익률</span><span>HERD</span><span>신호</span>
        </div>
        {sortedPortfolio.map((item) => (
          <HoldingRow
            key={item.ticker}
            item={item}
            row={rows.find((candidate) => candidate.ticker === item.ticker)}
            herd={herdMap[item.ticker]}
            price={priceMap[item.ticker]}
            editMode={editMode}
            deletingTicker={deletingTicker}
            targetWeight={targetWeights[item.ticker]}
            displayAmount={displayAmount}
            displayPnl={displayPnl}
            onDelete={onDelete}
            onOpenStock={onOpenStock}
            onEditHolding={onEditHolding}
            onTargetWeightChange={onTargetWeightChange}
          />
        ))}
      </div>
    </>
  )
}

function HoldingRow({
  item, row, herd, price, editMode, deletingTicker, targetWeight,
  displayAmount, displayPnl, onDelete, onOpenStock, onEditHolding, onTargetWeightChange,
}) {
  const stage = herd?.herdStage ?? 'Calm'
  const color = stageColor(stage)
  const stageName = stage.startsWith('Herd ') ? stage.slice(5) : stage
  const herdScore = herd ? Math.round(herd.herdV4 ?? herd.herdScore) : null
  const positionAction = herd ? buildPositionAction(herd, row) : null
  const signal = signalStyle(herd?.signal)
  const actionColor = positionAction?.muted ? 'var(--calm)' : signal.color
  const hasAvgPrice = item.avgPrice != null && item.quantity != null
  const isDeleting = deletingTicker === item.ticker
  const pnlUsd = hasAvgPrice && price
    ? price.market_value - item.avgPrice * item.quantity
    : null

  return (
    <div
      className={`${styles.holdingRow} ${editMode ? styles.holdingRowEdit : ''}`}
      onClick={editMode ? undefined : () => onOpenStock(item.ticker)}
      style={{ opacity: isDeleting ? 0.4 : 1 }}
    >
      <div className={styles.cardStripe} style={{ background: color, color }} />

      {editMode && (
        <button
          className={styles.cardDeleteBtn}
          onClick={(event) => onDelete(event, item.ticker)}
          disabled={!!deletingTicker}
          title={`${item.ticker} 포트폴리오에서 삭제`}
        >
          {isDeleting ? '…' : '✕'}
        </button>
      )}

      <div className={styles.holdingStockCell}>
        <StockAvatar ticker={item.ticker} logoUrl={herd?.logoUrl} tone={badgeStyle(stage)} size="lg" />
        <div className={styles.holdingStockText}>
          <strong>{item.ticker}</strong>
          <span style={{ color }}>{stageName}{herdScore != null ? ` · HERD ${herdScore}` : ''}</span>
          {shouldShowQuality(herd) && (
            <em style={{ color: qualityColor(herd.qualityLevel) }} title={qualityReasonText(herd)}>
              {qualityWarningText(herd)}
            </em>
          )}
        </div>
      </div>

      <div className={styles.holdingMetric}>
        <span>{row ? `${row.currentWeight.toFixed(1)}%` : '—'}</span>
        <em>{row ? `목표 ${row.targetWeight.toFixed(1)}%` : '목표 —'}</em>
        {row && <small>{fmtWeightGap(row)}</small>}
      </div>

      <div className={styles.holdingMetric}>
        <span>{price ? displayAmount(price.market_value) : '—'}</span>
        <em>{hasAvgPrice ? `보유 ${fmtShares(item.quantity)}` : '수량 미입력'}</em>
        {hasAvgPrice && <small>평단 {displayAmount(item.avgPrice)}</small>}
      </div>

      <div className={styles.holdingMetric}>
        <span style={{ color: pctColor(price?.return_pct) }}>{price ? fmtPct(price.return_pct) : '—'}</span>
        <em style={{ color: pctColor(price?.return_pct) }}>{pnlUsd != null ? displayPnl(pnlUsd) : '평단 필요'}</em>
        {price && <small style={{ color: pctColor(price.daily_change_pct) }}>오늘 {fmtPct(price.daily_change_pct)}</small>}
      </div>

      <div className={styles.holdingHerdCell}>
        {herd ? (
          <><strong style={{ color }}>{herdScore}</strong><span style={{ color }}>{stageName}</span>
            {formatSignalAgeLabel(herd) && <em>{formatSignalAgeLabel(herd)}</em>}</>
        ) : <span className={styles.cardDash}>—</span>}
      </div>

      <div className={styles.holdingActionCell}>
        {herd ? (
          <><strong style={{ color: actionColor }}>{positionAction.code}</strong>
            <span>{positionAction.text}</span><em>{positionAction.basis}</em></>
        ) : <span className={styles.cardDash}>—</span>}
      </div>

      {editMode && (
        <div className={styles.holdingEditTray} onClick={(event) => event.stopPropagation()}>
          <button className={styles.cardInputBtn} onClick={() => onEditHolding(item.ticker)}>
            {hasAvgPrice ? '평단·수량 수정' : '평단·수량 입력'}
          </button>
          {row && (
            <div className={styles.targetEditRow}>
              <label className={styles.targetLabel} htmlFor={`target-${item.ticker}`}>목표 비중</label>
              <div className={styles.targetInputWrap}>
                <input
                  id={`target-${item.ticker}`}
                  className={styles.targetInput}
                  type="number" min="0" max="100" step="1"
                  value={targetWeight ?? ''}
                  placeholder={row.targetWeight.toFixed(0)}
                  onChange={(event) => onTargetWeightChange(item.ticker, event.target.value)}
                  aria-label={`${item.ticker} 목표 비중`}
                />
                <span>%</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
