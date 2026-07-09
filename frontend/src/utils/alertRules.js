/**
 * alertRules.js — HERD 알림 조건 엔진.
 *
 * 브라우저 푸시/이메일 연동 전 단계로, 화면에서 동일한 규칙으로 알림 후보를 만든다.
 */

function num(value, fallback = 0) {
  if (value == null || value === '') return fallback
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function isBuySignal(signal) {
  return signal === 'BUY' || signal === 'ADD'
}

function isSellSignal(signal) {
  return signal === 'SELL' || signal === 'REDUCE'
}

function actionScore(row) {
  return num(row?.herd?.actionScore)
}

function signalDays(row) {
  return num(row?.herd?.signalDurationDays)
}

export function alertSeverityLabel(severity) {
  switch (severity) {
    case 'HIGH': return '중요'
    case 'MEDIUM': return '점검'
    case 'LOW': return '참고'
    default: return '정보'
  }
}

export function buildPortfolioAlerts(rows, riskWarnings = []) {
  const alerts = []

  rows.forEach((row) => {
    const signal = row.signal
    const score = num(row.herd?.herdV4 ?? row.herd?.herdScore, 50)
    const drift = num(row.drift)
    const strength = actionScore(row)
    const days = signalDays(row)

    if (isBuySignal(signal) && drift < -5 && strength >= 40) {
      alerts.push({
        id: `buy-${row.ticker}`,
        severity: strength >= 60 ? 'HIGH' : 'MEDIUM',
        type: 'BUY',
        ticker: row.ticker,
        title: `${row.ticker} 목표비중 부족`,
        value: `${Math.abs(drift).toFixed(1)}%p`,
        detail: `HERD ${Math.round(score)} · 분할매수 후보`,
        priority: 90 + strength,
      })
    }

    if (isSellSignal(signal) && drift > 3) {
      alerts.push({
        id: `sell-${row.ticker}`,
        severity: signal === 'SELL' ? 'HIGH' : 'MEDIUM',
        type: 'SELL',
        ticker: row.ticker,
        title: `${row.ticker} 비중 축소 후보`,
        value: `${drift.toFixed(1)}%p 초과`,
        detail: `HERD ${Math.round(score)} · 쏠림 구간`,
        priority: 80 + Math.abs(drift),
      })
    }

    if ((isBuySignal(signal) || isSellSignal(signal)) && days > 45) {
      alerts.push({
        id: `stale-${row.ticker}`,
        severity: 'LOW',
        type: 'STALE',
        ticker: row.ticker,
        title: `${row.ticker} 오래된 신호`,
        value: `${Math.round(days)}일째`,
        detail: '추격 대응보다 다음 전환 확인 우선',
        priority: 40 + Math.min(30, days / 3),
      })
    }
  })

  riskWarnings
    .filter((item) => item.level && item.level !== 'CLEAR')
    .forEach((item, index) => {
      alerts.push({
        id: `risk-${index}-${item.title}`,
        severity: item.level === 'HIGH' ? 'HIGH' : 'MEDIUM',
        type: 'RISK',
        ticker: null,
        title: item.title,
        value: item.value,
        detail: item.detail,
        priority: item.level === 'HIGH' ? 120 - index : 75 - index,
      })
    })

  return alerts
    .sort((a, b) => b.priority - a.priority)
    .slice(0, 5)
}
