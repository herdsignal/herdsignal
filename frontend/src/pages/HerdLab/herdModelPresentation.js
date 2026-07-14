const number = (value) => {
  if (value === null || value === undefined || value === '') return null
  return Number.isFinite(Number(value)) ? Number(value) : null
}

export function formatPercent(value, suffix = '%') {
  const parsed = number(value)
  if (parsed === null) return '—'
  return `${parsed > 0 ? '+' : ''}${parsed.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}${suffix}`
}

export function presentValidationReport(report) {
  const walk = report.walkForward
  const run = report.validationRun
  const stability = report.parameterStability
  const dsrPassed = report.overfitting?.deflatedSharpeStatus === 'PASS'
  const gate = report.adoptionGate
  const generatedAt = report.generatedAt
    ? new Date(report.generatedAt).toLocaleString('ko-KR')
    : '생성 시각 없음'

  return {
    model: {
      version: report.modelVersion,
      period: '전체 저장 기간',
      generatedAt,
      status: gate?.status ?? 'RESEARCH_VALIDATION',
    },
    metrics: [
      { label: 'OOS 수익 개선', value: formatPercent(walk?.improvementRate), sub: `${walk?.samples ?? 0}개 Walk-forward 구간`, tone: 'blue' },
      { label: 'OOS MDD 개선', value: formatPercent(walk?.mddImprovementMedian, '%p'), sub: '중앙값', tone: 'green' },
      { label: '파라미터 유지율', value: formatPercent(stability?.sameParameterRate), sub: stability?.recommendation ?? '판정 없음', tone: 'slate' },
      { label: 'DSR 검증', value: dsrPassed ? '통과' : '미달', sub: `시험 ${report.overfitting?.parametersTested ?? 0}개`, tone: 'orange' },
    ],
    trustChecks: [
      { label: '검증 완주', value: `${run?.completedTickers ?? 0}/${run?.requestedTickers ?? 0}`, sub: formatPercent((run?.coverage ?? 0) * 100) },
      { label: 'OOS 엠바고', value: `${run?.embargoDays ?? 0}일`, sub: '학습 경계 제외' },
      { label: '점수 재현', value: report.scoreParityPassed ? '통과' : '실패', sub: 'Python ↔ Backend' },
      { label: '생존편향', value: report.survivorshipStatus === 'SURVIVORSHIP_BIAS_REMAINS' ? '남아있음' : '완화', sub: '해석 시 주의' },
    ],
    modelNotes: [
      `HERD v4는 운영 상태 점수이고 ${report.modelVersion} Action Layer는 아직 연구 검증 중입니다.`,
      `Walk-forward OOS ${walk?.samples ?? 0}구간의 수익 개선 비율은 ${formatPercent(walk?.improvementRate)}, MDD 개선 중앙값은 ${formatPercent(walk?.mddImprovementMedian, '%p')}입니다.`,
      stability?.singleParameterSpike
        ? '특정 파라미터에서 성과가 튀어 고정 파라미터 사용이 권고됩니다.'
        : '인접 파라미터에서도 결과가 비교적 안정적입니다.',
      gate?.eligibleForHumanReview
        ? `게이트 ${gate.policyVersion}을 통과해 운영 승격 검토가 가능합니다. 자동 운영 전환은 하지 않습니다.`
        : `게이트 ${gate?.policyVersion ?? '미설정'} 미통과: ${(gate?.failedCriteria ?? []).join(', ') || '판정 정보 없음'}`,
      '표시되는 행동은 확정 매매 추천이 아니라 장기투자 판단을 돕는 연구 정보입니다.',
    ],
    rows: (report.tickers ?? []).map((row) => {
      const capture = number(row.capture)
      const mdd = number(row.mddImprovement)
      const pass = capture !== null && capture >= 60 && mdd !== null && mdd >= 0
      return {
        ticker: row.ticker,
        buyHold: formatPercent(row.buyHoldReturn),
        action: formatPercent(row.actionReturn),
        capture: formatPercent(row.capture),
        mdd: formatPercent(row.mddImprovement, '%p'),
        actions: `${row.actions ?? 0}회`,
        verdict: pass ? '기준 통과' : '추가 검증',
        tone: pass ? 'pass' : 'watch',
      }
    }),
  }
}
