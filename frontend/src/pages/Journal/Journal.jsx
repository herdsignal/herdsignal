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
  formatJournalDate,
  formatJournalDuration,
  formatHorizonOutcome,
  formatJournalPrice,
  formatJournalProfit,
  formatJournalQuantity,
  formatJournalTime,
  filterSignalJournal,
  findHorizonOutcome,
  getJournalReviewStatus,
  summarizeSignalJournal,
} from '../../utils/signalJournal'
import styles from './Journal.module.css'

const FILTERS = [
  { value: 'ALL', label: '전체' },
  { value: 'BUY', label: '매수' },
  { value: 'SELL', label: '익절' },
  { value: 'HOLD', label: '보류' },
]

const REVIEW_FILTERS = [
  { value: 'ALL', label: '전체 결과' },
  { value: 'READY', label: '확인 가능' },
  { value: 'PENDING', label: '대기 중' },
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
  const [reviewFilter, setReviewFilter] = useState('ALL')
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
    return filterSignalJournal(logs, filter, reviewFilter)
  }, [filter, logs, reviewFilter])

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
        <div className={styles.summaryCard}>
          <span>결과 확인</span>
          <strong>{formatJournalCount(summary.outcomeAvailableCount)}</strong>
          <em>1·3·6개월 종가 기준</em>
        </div>
      </div>

      <div className={styles.tableCard}>
        <div className={styles.tableHead}>
          <div>
            <span>기록 {formatJournalCount(filteredLogs.length)}</span>
            <strong>{filter === 'ALL' ? '전체 판단' : FILTERS.find((item) => item.value === filter)?.label}</strong>
          </div>
          <div className={styles.reviewTabs} aria-label="결과 확인 필터">
            {REVIEW_FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`${styles.reviewBtn} ${reviewFilter === item.value ? styles.reviewBtnActive : ''}`}
                onClick={() => setReviewFilter(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
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
            <strong>{reviewFilter === 'ALL' ? '아직 기록이 없습니다.' : '조건에 맞는 기록이 없습니다.'}</strong>
            <span>
              {reviewFilter === 'PENDING'
                ? '결과를 기다리는 기록이 없습니다.'
                : reviewFilter === 'READY'
                  ? '1·3·6개월 중 확인 가능한 결과가 아직 없습니다.'
                  : '종목 상세에서 HERD 판단을 남기면 여기에 쌓입니다.'}
            </span>
          </div>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>종목</th>
                  <th>판단</th>
                  <th>체결 정보</th>
                  <th>기록 수익률</th>
                  <th>1·3·6개월</th>
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
                      <div className={styles.horizonStack}>
                        <em className={`${styles.reviewStatus} ${styles[getJournalReviewStatus(log).toLowerCase()]}`}>
                          {getJournalReviewStatus(log) === 'READY'
                            ? '결과 확인 가능'
                            : getJournalReviewStatus(log) === 'PENDING'
                              ? '기간 경과 대기'
                              : '가격 자료 없음'}
                        </em>
                        {[
                          ['1M', '1개월'],
                          ['3M', '3개월'],
                          ['6M', '6개월'],
                        ].map(([horizon, label]) => {
                          const outcome = findHorizonOutcome(log, horizon)
                          const returnValue = outcome?.status === 'AVAILABLE'
                            ? Number(outcome.returnPct)
                            : null
                          return (
                            <span key={horizon}>
                              <small>{label}</small>
                              <strong className={
                                returnValue == null
                                  ? ''
                                  : returnValue >= 0 ? styles.positive : styles.negative
                              }>
                                {formatHorizonOutcome(outcome)}
                              </strong>
                            </span>
                          )
                        })}
                        <em>
                          기준 {formatJournalPrice(log.referencePrice) ?? '—'}
                          {log.referencePriceDate
                            ? ` · ${formatJournalDate(log.referencePriceDate)}`
                            : ''}
                        </em>
                      </div>
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
