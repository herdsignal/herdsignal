import { useState } from 'react'
import HerdLens from '../../components/HerdLens/HerdLens'
import StockAvatar from '../../components/StockAvatar/StockAvatar'
import { fmtPct, fmtShares } from './portfolioPresentation'
import { PORTFOLIO_SORTS } from './portfolioModel'
import styles from './Portfolio.module.css'

function toneClass(value) {
  if (value == null || Number(value) === 0) return ''
  return Number(value) > 0 ? styles.positive : styles.negative
}

export default function PortfolioHoldings({
  rows,
  sortBy,
  deletingTicker,
  displayAmount,
  displaySignedAmount,
  onSortChange,
  onOpenStock,
  onEditHolding,
  onDelete,
}) {
  const [expandedTicker, setExpandedTicker] = useState(null)

  return (
    <section className={styles.holdingsSection} aria-labelledby="holdings-title">
      <div className={styles.sectionHeader}>
        <div>
          <h2 id="holdings-title">보유 종목</h2>
          <span>{rows.length}개</span>
        </div>
        <div className={styles.sortTabs} aria-label="보유 종목 정렬">
          {PORTFOLIO_SORTS.map((item) => (
            <button
              type="button"
              key={item.value}
              className={sortBy === item.value ? styles.activeTab : ''}
              aria-pressed={sortBy === item.value}
              onClick={() => onSortChange(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.holdingsTable}>
        <div className={styles.holdingsHead} aria-hidden="true">
          <span>종목</span>
          <span>평가금액 · 비중</span>
          <span>평가손익률</span>
          <span>오늘</span>
          <span>HERD · 4주</span>
          <span>관리</span>
        </div>
        {rows.map((row) => {
          const expanded = expandedTicker === row.ticker
          return (
            <article className={styles.holding} key={row.ticker}>
              <div className={styles.holdingRow}>
                <button
                  type="button"
                  className={styles.holdingSummary}
                  aria-label={`${row.ticker} 종목 상세 열기`}
                  onClick={() => onOpenStock(row.ticker)}
                >
                  <span className={styles.stockIdentity}>
                    <StockAvatar
                      ticker={row.ticker}
                      logoUrl={row.logoUrl}
                      size="md"
                    />
                    <span>
                      <strong>{row.ticker}</strong>
                      <small>{row.companyName ?? '보유 종목'}</small>
                    </span>
                  </span>
                  <span className={styles.amountCell}>
                    <strong>{displayAmount(row.marketValue)}</strong>
                    <small>{row.weightPct == null ? '—' : `${row.weightPct.toFixed(1)}%`}</small>
                  </span>
                  <span className={toneClass(row.returnPct)}>
                    <strong>{fmtPct(row.returnPct)}</strong>
                    <small>{displaySignedAmount(row.pnl)}</small>
                  </span>
                  <span className={toneClass(row.dailyChangePct)}>
                    <strong>{fmtPct(row.dailyChangePct)}</strong>
                    <small>전일 대비</small>
                  </span>
                  <HerdLens
                    compact
                    score={row.herdScore}
                    stage={row.herdStage}
                    previousScore={row.herdPreviousScore}
                  />
                </button>
                <button
                  type="button"
                  className={styles.holdingManage}
                  aria-label={`${row.ticker} 보유 정보 관리`}
                  aria-expanded={expanded}
                  aria-controls={`holding-${row.ticker}`}
                  onClick={() => setExpandedTicker(expanded ? null : row.ticker)}
                >
                  {expanded ? '닫기' : '관리'}
                </button>
              </div>

              {expanded && (
                <div className={styles.holdingDetails} id={`holding-${row.ticker}`}>
                  <dl>
                    <div><dt>현재가</dt><dd>{displayAmount(row.currentPrice)}</dd></div>
                    <div><dt>평균 매수가</dt><dd>{displayAmount(row.avgPrice)}</dd></div>
                    <div><dt>수량</dt><dd>{fmtShares(row.quantity)}</dd></div>
                    <div><dt>매입금액</dt><dd>{displayAmount(row.cost)}</dd></div>
                    <div>
                      <dt>평가손익률</dt>
                      <dd className={toneClass(row.returnPct)}>{fmtPct(row.returnPct)}</dd>
                    </div>
                    <div>
                      <dt>오늘</dt>
                      <dd className={toneClass(row.dailyChangePct)}>{fmtPct(row.dailyChangePct)}</dd>
                    </div>
                    <div>
                      <dt>HERD 4주 전</dt>
                      <dd>{row.herdPreviousScore == null ? '—' : Math.round(row.herdPreviousScore)}</dd>
                    </div>
                    <div><dt>관찰일</dt><dd>{row.observationDate ?? '—'}</dd></div>
                  </dl>
                  <div className={styles.rowActions}>
                    <button type="button" onClick={() => onOpenStock(row.ticker)}>
                      종목 분석
                    </button>
                    <button type="button" onClick={() => onEditHolding(row.ticker)}>
                      평단·수량 수정
                    </button>
                    <button
                      type="button"
                      className={styles.removeButton}
                      disabled={Boolean(deletingTicker)}
                      onClick={(event) => onDelete(event, row.ticker)}
                    >
                      {deletingTicker === row.ticker ? '삭제 중…' : '삭제'}
                    </button>
                  </div>
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
