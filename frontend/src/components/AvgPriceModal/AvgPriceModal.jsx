/**
 * AvgPriceModal.jsx — 평균 매수가·수량 입력 모달
 *
 * Props:
 *   ticker          — 대상 종목 티커
 *   currentAvgPrice — 기존 평균 매수가 (없으면 null)
 *   currentQuantity — 기존 보유 수량  (없으면 null)
 *   onClose         — 모달 닫기 콜백
 *   onSaved         — 저장 성공 콜백 (부모에서 데이터 재조회)
 */

import { useState } from 'react'
import { updateAvgPrice } from '../../api/herdApi'
import styles from './AvgPriceModal.module.css'

export default function AvgPriceModal({
  ticker,
  currentAvgPrice,
  currentQuantity,
  onClose,
  onSaved,
}) {
  const [avgPrice, setAvgPrice] = useState(currentAvgPrice ?? '')
  const [quantity, setQuantity] = useState(currentQuantity ?? '')
  const [saving,   setSaving]   = useState(false)
  const [error,    setError]    = useState(null)

  /* 저장 처리 */
  const handleSave = async () => {
    if (!avgPrice || !quantity) {
      setError('평단가와 수량을 모두 입력해주세요.')
      return
    }
    const avg = parseFloat(avgPrice)
    const qty = parseFloat(quantity)
    if (isNaN(avg) || avg <= 0 || isNaN(qty) || qty <= 0) {
      setError('유효한 숫자를 입력해주세요.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await updateAvgPrice(ticker, avg, qty)
      /* 저장된 값을 부모에 전달 → 부모가 로컬 상태 즉시 업데이트 */
      onSaved(avg, qty)
    } catch {
      setError('저장 중 오류가 발생했습니다. 다시 시도해주세요.')
    } finally {
      setSaving(false)
    }
  }

  /* Enter 키로 저장 */
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') onClose()
  }

  return (
    /* 오버레이 클릭 → 닫기 */
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* 헤더 */}
        <div className={styles.header}>
          <span className={styles.title}>
            <span className={styles.ticker}>{ticker}</span>
            {/* 기존 평단가 여부에 따라 제목 구분 */}
            {currentAvgPrice != null ? ' 평단가 수정' : ' 평단가 입력'}
          </span>
          <button
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="모달 닫기"
          >
            ✕
          </button>
        </div>

        {/* 입력 필드 */}
        <div className={styles.body}>
          <div className={styles.field}>
            <label className={styles.fieldLabel}>평균 매수가 (USD)</label>
            <input
              className={styles.input}
              type="number"
              value={avgPrice}
              onChange={(e) => setAvgPrice(e.target.value)}
              placeholder="예: 150.00"
              step="0.01"
              min="0"
              autoFocus
            />
          </div>
          <div className={styles.field}>
            <label className={styles.fieldLabel}>보유 수량 (주)</label>
            <input
              className={styles.input}
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="예: 10"
              step="0.0001"
              min="0"
            />
          </div>
          {error && <p className={styles.errorMsg}>{error}</p>}
        </div>

        {/* 버튼 */}
        <div className={styles.footer}>
          <button className={styles.cancelBtn} onClick={onClose} disabled={saving}>
            취소
          </button>
          <button
            className={styles.saveBtn}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? '저장 중…' : '저장'}
          </button>
        </div>
      </div>
    </div>
  )
}
