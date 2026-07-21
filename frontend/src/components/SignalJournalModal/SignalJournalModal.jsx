/**
 * SignalJournalModal.jsx — HERD 판단 기록 입력 모달
 *
 * StockDetail에서 HERD 신호를 보고 실제 매수/보류/익절 판단을 남길 때 사용한다.
 * 저장 자체는 부모가 localStorage 유틸로 처리한다.
 */

import { useMemo, useState } from 'react'
import styles from './SignalJournalModal.module.css'

const ACTION_META = {
  BUY: {
    title: '매수 기록',
    priceLabel: '매수가 (USD)',
    quantityLabel: '매수 수량 (주)',
    memoPlaceholder: '예: Flee 신호라 1차 분할매수',
  },
  HOLD: {
    title: '보류 기록',
    priceLabel: '확인 가격 (USD)',
    quantityLabel: '대상 수량 (선택)',
    memoPlaceholder: '예: 목표 비중 초과라 보류',
  },
  SELL: {
    title: '익절/축소 기록',
    priceLabel: '매도가 (USD)',
    quantityLabel: '매도 수량 (주)',
    memoPlaceholder: '예: 목표 비중 초과로 5% 축소',
  },
}

function toNumber(value) {
  if (value === '' || value == null) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export default function SignalJournalModal({
  ticker,
  actionType,
  herdSnapshot,
  onClose,
  onSave,
}) {
  const meta = ACTION_META[actionType] ?? ACTION_META.HOLD
  const [price, setPrice] = useState('')
  const [quantity, setQuantity] = useState('')
  const [profitPct, setProfitPct] = useState('')
  const [memo, setMemo] = useState('')
  const [error, setError] = useState(null)

  const amount = useMemo(() => {
    const p = toNumber(price)
    const q = toNumber(quantity)
    if (p == null || q == null) return null
    return p * q
  }, [price, quantity])

  function handleSave() {
    const p = toNumber(price)
    const q = toNumber(quantity)
    const profit = toNumber(profitPct)

    if ((actionType === 'BUY' || actionType === 'SELL') && (p == null || p <= 0 || q == null || q <= 0)) {
      setError('가격과 수량을 모두 입력해주세요.')
      return
    }
    if (actionType === 'HOLD' && price && (p == null || p <= 0)) {
      setError('가격은 0보다 큰 숫자로 입력해주세요.')
      return
    }
    if (profitPct && profit == null) {
      setError('수익률은 숫자로 입력해주세요.')
      return
    }

    onSave({
      price: p,
      quantity: q,
      amount,
      profitPct: actionType === 'SELL' ? profit : null,
      memo: memo.trim(),
    })
  }

  function handleKeyDown(e) {
    if (e.key === 'Escape') onClose()
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave()
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className={styles.header}>
          <div>
            <div className={styles.eyebrow}>HERD 판단 기록</div>
            <div className={styles.title}>
              <span>{ticker}</span> {meta.title}
            </div>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="모달 닫기">
            ×
          </button>
        </div>

        <div className={styles.snapshot}>
          <div>
            <span>HERD</span>
            <strong>{herdSnapshot.score}</strong>
          </div>
          <div>
            <span>단계</span>
            <strong>{herdSnapshot.stage}</strong>
          </div>
          <div>
            <span>신호</span>
            <strong>{herdSnapshot.signalLabel}</strong>
          </div>
        </div>

        <div className={styles.body}>
          <div className={styles.fieldGrid}>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>{meta.priceLabel}</label>
              <input
                className={styles.input}
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="예: 185.50"
                step="0.01"
                min="0"
                autoFocus
              />
            </div>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>{meta.quantityLabel}</label>
              <input
                className={styles.input}
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="예: 3"
                step="0.0001"
                min="0"
              />
            </div>
          </div>

          {actionType === 'SELL' && (
            <div className={styles.field}>
              <label className={styles.fieldLabel}>실현 수익률 (%)</label>
              <input
                className={styles.input}
                type="number"
                value={profitPct}
                onChange={(e) => setProfitPct(e.target.value)}
                placeholder="예: 18.5"
                step="0.1"
              />
            </div>
          )}

          <div className={styles.field}>
            <label className={styles.fieldLabel}>메모</label>
            <textarea
              className={styles.textarea}
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder={meta.memoPlaceholder}
              rows={3}
            />
          </div>

          <div className={styles.amountBox}>
            <span>기록 총액</span>
            <strong>{amount == null ? '—' : `$${amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}</strong>
          </div>

          {error && <p className={styles.errorMsg}>{error}</p>}
        </div>

        <div className={styles.footer}>
          <button className={styles.cancelBtn} onClick={onClose}>취소</button>
          <button className={styles.saveBtn} onClick={handleSave}>기록 저장</button>
        </div>
      </div>
    </div>
  )
}
