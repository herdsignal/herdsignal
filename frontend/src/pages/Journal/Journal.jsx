/**
 * Journal.jsx — 전체 HERD 판단 기록 (/journal)
 *
 * StockDetail에서 DB에 저장한 signal_journal을 전체 종목 기준으로 보여준다.
 */

import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSignalJournal } from '../../api/herdApi'
import {
  formatJournalAmount,
  formatJournalCount,
  formatJournalDuration,
  formatJournalPrice,
  formatJournalProfit,
  formatJournalQuantity,
  formatJournalTime,
  summarizeSignalJournal,
} from '../../utils/signalJournal'
import styles from './Journal.module.css'

const FILTERS = [
  { value: 'ALL', label: '전체' },
  { value: 'BUY', label: '매수' },
  { value: 'SELL', label: '익절' },
  { value: 'HOLD', label: '보류' },
]

function actionText(log) {
  if (log.actionLabel) return log.actionLabel
  switch (log.actionType) {
    case 'BUY': return '매수'
    case 'SELL': return '익절'
    case 'HOLD': return '보류'
    default: return '기록'
  }
}

function actionClass(type) {
  switch (type) {
    case 'BUY': return styles.buy
    case 'SELL': return styles.sell
    case 'HOLD': return styles.hold
    default: return ''
  }
}

export default function Journal() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('ALL')
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getSignalJournal()
      .then((res) => setLogs(res.data?.data ?? []))
      .catch(() => setError('판단 기록을 불러올 수 없습니다.'))
      .finally(() => setLoading(false))
  }, [])

  const filteredLogs = useMemo(() => {
    if (filter === 'ALL') return logs
    return logs.filter((log) => log.actionType === filter)
  }, [filter, logs])

  const summary = useMemo(() => summarizeSignalJournal(logs), [logs])

  const today = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <div className={styles.pageDate}>{today}</div>
          <h1 className={styles.pageTitle}>판단 기록</h1>
        </div>
        <div className={styles.filterTabs} aria-label="판단 기록 필터">
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`${styles.filterBtn} ${filter === item.value ? styles.filterBtnActive : ''}`}
              onClick={() => setFilter(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.summaryGrid}>
        <div className={styles.summaryCard}>
          <span>전체 기록</span>
          <strong>{formatJournalCount(summary.totalCount)}</strong>
          <em>HERD 기준 판단</em>
        </div>
        <div className={styles.summaryCard}>
          <span>매수 총액</span>
          <strong>{formatJournalAmount(summary.buyAmount) ?? '$0'}</strong>
          <em>{formatJournalCount(summary.buyCount)}</em>
        </div>
        <div className={styles.summaryCard}>
          <span>익절 총액</span>
          <strong>{formatJournalAmount(summary.sellAmount) ?? '$0'}</strong>
          <em>{formatJournalCount(summary.sellCount)}</em>
        </div>
        <div className={styles.summaryCard}>
          <span>평균 익절률</span>
          <strong>{summary.hasProfitData ? formatJournalProfit(summary.avgProfitPct) : '—'}</strong>
          <em>익절 기록 기준</em>
        </div>
      </div>

      <div className={styles.tableCard}>
        <div className={styles.tableHead}>
          <span>기록 {formatJournalCount(filteredLogs.length)}</span>
          <strong>{filter === 'ALL' ? '전체' : FILTERS.find((item) => item.value === filter)?.label}</strong>
        </div>

        {loading ? (
          <div className={styles.emptyState}>
            <strong>기록을 불러오는 중입니다.</strong>
            <span>저장된 HERD 판단 기록을 확인하고 있습니다.</span>
          </div>
        ) : error ? (
          <div className={styles.emptyState}>
            <strong>{error}</strong>
            <span>백엔드 서버와 DB 상태를 확인해주세요.</span>
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className={styles.emptyState}>
            <strong>아직 기록이 없습니다.</strong>
            <span>종목 상세에서 HERD 판단을 남기면 여기에 쌓입니다.</span>
          </div>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>종목</th>
                  <th>판단</th>
                  <th>체결 정보</th>
                  <th>수익률</th>
                  <th>HERD 신호</th>
                  <th>메모</th>
                  <th>날짜</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log) => (
                  <tr key={log.id} onClick={() => navigate(`/stock/${log.ticker}`)}>
                    <td>
                      <button type="button" className={styles.tickerBtn}>
                        {log.ticker}
                      </button>
                    </td>
                    <td>
                      <span className={`${styles.actionBadge} ${actionClass(log.actionType)}`}>
                        {actionText(log)}
                      </span>
                    </td>
                    <td>
                      <div className={styles.tradeStack}>
                        <strong>{formatJournalAmount(log.amount) ?? '금액 미입력'}</strong>
                        <span>
                          {formatJournalPrice(log.price) ?? '가격 —'} · {formatJournalQuantity(log.quantity) ?? '수량 —'}
                        </span>
                      </div>
                    </td>
                    <td className={Number(log.profitPct) >= 0 ? styles.positive : styles.negative}>
                      {formatJournalProfit(log.profitPct) ?? '—'}
                    </td>
                    <td>
                      <div className={styles.signalStack}>
                        <strong>
                          {log.herdScore != null
                            ? `${Math.round(Number(log.herdScore))}${log.herdStage ? ` · ${log.herdStage}` : ''}`
                            : '—'}
                        </strong>
                        <span>{formatJournalDuration(log.signalDurationDays) ?? log.signal ?? '신호 —'}</span>
                      </div>
                    </td>
                    <td>
                      <span className={styles.memoCell}>{log.memo || '—'}</span>
                    </td>
                    <td>{formatJournalTime(log.recordedAt ?? log.createdAt) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
