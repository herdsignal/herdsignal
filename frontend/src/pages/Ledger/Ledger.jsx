import { useCallback, useEffect, useState } from 'react'
import {
  createPortfolioLedgerEntry,
  deletePortfolioLedgerEntry,
  exportPortfolioLedgerCsv,
  getPortfolioLedger,
  getPortfolioLedgerSummary,
  getPortfolioSourceReconciliation,
} from '../../api/herdApi'
import {
  ENTRY_TYPES,
  entryPayload,
  formatSignedUsd,
  formatUsd,
  isTrade,
  needsTicker,
} from './ledgerModel'
import styles from './Ledger.module.css'

const initialForm = {
  entryType: 'BUY',
  ticker: '',
  occurredOn: new Date().toISOString().slice(0, 10),
  quantity: '',
  unitPrice: '',
  amount: '',
  fee: '',
  splitRatio: '',
  note: '',
}

export default function Ledger() {
  const [entries, setEntries] = useState([])
  const [summary, setSummary] = useState(null)
  const [reconciliation, setReconciliation] = useState(null)
  const [form, setForm] = useState(initialForm)
  const [formOpen, setFormOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [entriesResponse, summaryResponse, reconciliationResponse] = await Promise.all([
        getPortfolioLedger(),
        getPortfolioLedgerSummary(),
        getPortfolioSourceReconciliation(),
      ])
      setEntries(entriesResponse.data?.data ?? [])
      setSummary(summaryResponse.data?.data ?? null)
      setReconciliation(reconciliationResponse.data?.data ?? null)
    } catch (requestError) {
      setError(requestError.response?.data?.message || '거래 원장을 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const update = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await createPortfolioLedgerEntry(entryPayload(form))
      setForm((current) => ({ ...initialForm, entryType: current.entryType }))
      setFormOpen(false)
      await load()
    } catch (requestError) {
      setError(requestError.response?.data?.message || '원장 항목을 저장하지 못했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('이 원장 항목을 삭제할까요?')) return
    try {
      await deletePortfolioLedgerEntry(id)
      await load()
    } catch (requestError) {
      setError(requestError.response?.data?.message || '원장 항목을 삭제하지 못했습니다.')
    }
  }

  const exportCsv = async () => {
    try {
      const response = await exportPortfolioLedgerCsv()
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'herdsignal-ledger.csv'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('CSV를 내보내지 못했습니다.')
    }
  }

  const statusMessage = {
    EMPTY_LEDGER: '입금과 거래를 실제 발생 순서대로 기록하면 원가와 손익을 계산합니다.',
    INVALID_LEDGER: '보유 수량보다 많은 매도가 있어 계산을 중단했습니다.',
    PRICE_INCOMPLETE: '일부 종목의 최신 종가가 없어 계좌 평가를 숨겼습니다.',
    LEDGER_READY: 'FIFO 원가 기준 · 수수료 포함',
  }[summary?.status]
  const reconciliationMessage = {
    NO_LEDGER: '원장이 비어 있어 현재 보유 현황을 계속 기준으로 사용합니다.',
    LEDGER_INVALID: '원장 계산 오류가 있어 현재 보유 현황과 연결하지 않습니다.',
    DIVERGED: '현재 보유 현황과 원장 수량·현금이 달라 자동으로 전환하지 않습니다.',
    MATCHED: '현재 보유 현황과 원장이 일치합니다. 원장 기준 전환 준비가 됐습니다.',
  }[reconciliation?.status]

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>ACCOUNT LEDGER</span>
          <h1>거래 원장</h1>
          <p>입출금과 거래 사실을 한 통화(USD)로 기록합니다.</p>
        </div>
        <div className={styles.headerActions}>
          <button type="button" className={styles.secondary} onClick={exportCsv}>CSV 내보내기</button>
          <button type="button" className={styles.primary} onClick={() => setFormOpen((open) => !open)}>
            {formOpen ? '닫기' : '항목 기록'}
          </button>
        </div>
      </header>

      {error && <div className={styles.error} role="alert">{error}</div>}
      {!loading && reconciliationMessage && (
        <section
          className={`${styles.reconciliation} ${
            reconciliation?.ledgerCanBecomeSource ? styles.reconciliationReady : ''
          }`}
          aria-label="포트폴리오 기준 정합성"
        >
          <div>
            <span>PORTFOLIO SOURCE</span>
            <strong>{reconciliation?.status}</strong>
          </div>
          <p>{reconciliationMessage}</p>
          {reconciliation?.positionDifferences?.length > 0 && (
            <small>
              수량 차이 {reconciliation.positionDifferences.map((item) => item.ticker).join(', ')}
              {' · '}현금 차이 {formatSignedUsd(reconciliation.cashDifference)}
            </small>
          )}
        </section>
      )}

      {formOpen && (
        <form className={styles.form} onSubmit={submit}>
          <label>
            유형
            <select name="entryType" value={form.entryType} onChange={update}>
              {Object.entries(ENTRY_TYPES).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            날짜
            <input required type="date" name="occurredOn" value={form.occurredOn} onChange={update} />
          </label>
          {needsTicker(form.entryType) && (
            <label>
              티커
              <input required name="ticker" value={form.ticker} onChange={update} placeholder="NVDA" />
            </label>
          )}
          {isTrade(form.entryType) ? (
            <>
              <label>
                수량
                <input required min="0" step="0.000001" type="number" name="quantity" value={form.quantity} onChange={update} />
              </label>
              <label>
                체결 단가
                <input required min="0" step="0.000001" type="number" name="unitPrice" value={form.unitPrice} onChange={update} />
              </label>
              <label>
                수수료
                <input min="0" step="0.01" type="number" name="fee" value={form.fee} onChange={update} placeholder="0" />
              </label>
            </>
          ) : form.entryType === 'SPLIT' ? (
            <label>
              분할 배율
              <input required min="0" step="0.00000001" type="number" name="splitRatio" value={form.splitRatio} onChange={update} placeholder="예: 4대1은 4" />
            </label>
          ) : (
            <label>
              금액
              <input required min="0" step="0.01" type="number" name="amount" value={form.amount} onChange={update} />
            </label>
          )}
          <label className={styles.note}>
            메모
            <input maxLength="200" name="note" value={form.note} onChange={update} placeholder="선택" />
          </label>
          <button className={styles.primary} disabled={saving}>{saving ? '저장 중…' : '저장'}</button>
        </form>
      )}

      {!loading && summary && (
        <>
          <section className={styles.summary} aria-label="원장 요약">
            <div>
              <span>원장 계좌 가치</span>
              <strong>{formatUsd(summary.accountValue)}</strong>
            </div>
            <div>
              <span>현금</span>
              <strong>{formatUsd(summary.cashBalance)}</strong>
            </div>
            <div>
              <span>주식 평가액</span>
              <strong>{formatUsd(summary.marketValue)}</strong>
            </div>
            <div>
              <span>실현 손익</span>
              <strong>{formatSignedUsd(summary.realizedPnl)}</strong>
            </div>
            <div>
              <span>미실현 손익</span>
              <strong>{formatSignedUsd(summary.unrealizedPnl)}</strong>
            </div>
          </section>
          <p className={styles.status}>{statusMessage}</p>
          {[...(summary.errors ?? []), ...(summary.warnings ?? [])].map((message) => (
            <div key={message} className={styles.warning}>{message}</div>
          ))}

          {summary.positions?.length > 0 && (
            <section className={styles.positions}>
              <div className={styles.sectionTitle}>
                <h2>원장 보유</h2>
                <span>{summary.priceAsOf ? `${summary.priceAsOf} 종가` : '가격 미확인'}</span>
              </div>
              {summary.positions.map((position) => (
                <div className={styles.positionRow} key={position.ticker}>
                  <strong>{position.ticker}</strong>
                  <span>{Number(position.quantity).toLocaleString()}주</span>
                  <span>평균 {formatUsd(position.averageCost)}</span>
                  <span>{formatUsd(position.marketValue)}</span>
                  <span className={Number(position.unrealizedPnl) >= 0 ? styles.positive : styles.negative}>
                    {formatSignedUsd(position.unrealizedPnl)}
                  </span>
                </div>
              ))}
            </section>
          )}
        </>
      )}

      <section className={styles.entries}>
        <div className={styles.sectionTitle}>
          <h2>전체 항목</h2>
          <span>{entries.length}건</span>
        </div>
        {loading && <div className={styles.empty}>불러오는 중…</div>}
        {!loading && entries.length === 0 && <div className={styles.empty}>기록된 항목이 없습니다.</div>}
        {entries.map((entry) => (
          <div className={styles.entryRow} key={entry.id}>
            <time>{entry.occurredOn}</time>
            <strong>{ENTRY_TYPES[entry.entryType]}</strong>
            <span>{entry.ticker || '계좌'}</span>
            <span>{entry.quantity ? `${Number(entry.quantity).toLocaleString()}주` : entry.note || '—'}</span>
            <span className={Number(entry.cashEffect) >= 0 ? styles.positive : styles.negative}>
              {formatSignedUsd(entry.cashEffect)}
            </span>
            <button type="button" onClick={() => remove(entry.id)} aria-label={`${entry.occurredOn} ${ENTRY_TYPES[entry.entryType]} 삭제`}>
              삭제
            </button>
          </div>
        ))}
      </section>
    </div>
  )
}
