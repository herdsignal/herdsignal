const number = (value) => {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(String(value).replace(/[+%,p]/g, ''))
  return Number.isFinite(parsed) ? parsed : null
}

const SECTOR_BY_TICKER = {
  SPY: '시장 지수', QQQ: '시장 지수', IWM: '시장 지수', DIA: '시장 지수',
  AAPL: '기술', MSFT: '기술', NVDA: '기술', AVGO: '기술', ORCL: '기술', CRM: '기술',
  GOOGL: '커뮤니케이션', META: '커뮤니케이션', NFLX: '커뮤니케이션', DIS: '커뮤니케이션', TMUS: '커뮤니케이션',
  AMZN: '경기소비재', TSLA: '경기소비재', HD: '경기소비재', MCD: '경기소비재', NKE: '경기소비재',
  WMT: '필수소비재', COST: '필수소비재', PG: '필수소비재', KO: '필수소비재', PEP: '필수소비재',
  JPM: '금융', BAC: '금융', GS: '금융', V: '금융', MA: '금융',
  LLY: '헬스케어', UNH: '헬스케어', JNJ: '헬스케어', ABBV: '헬스케어', MRK: '헬스케어',
  GE: '산업재', CAT: '산업재', HON: '산업재', UNP: '산업재', BA: '산업재',
  XOM: '에너지', CVX: '에너지', COP: '에너지', SLB: '에너지', EOG: '에너지',
  NEE: '유틸리티', DUK: '유틸리티', SO: '유틸리티',
  AMT: '부동산', PLD: '부동산',
  LIN: '소재', APD: '소재', SHW: '소재', FCX: '소재', NEM: '소재',
}

const FEATURED_SECTORS = [
  { name: '기술', ticker: 'NVDA' },
  { name: '금융', ticker: 'JPM' },
  { name: '헬스케어', ticker: 'LLY' },
  { name: '경기소비재', ticker: 'AMZN' },
  { name: '산업재', ticker: 'GE' },
  { name: '에너지', ticker: 'XOM' },
]

function median(values) {
  const valid = values.filter((value) => value !== null).sort((a, b) => a - b)
  if (valid.length === 0) return null
  const middle = Math.floor(valid.length / 2)
  return valid.length % 2 === 0
    ? (valid[middle - 1] + valid[middle]) / 2
    : valid[middle]
}

export function summarizeFeaturedSectors(tickers = []) {
  return FEATURED_SECTORS.map((featured) => {
    const members = tickers.filter((row) => SECTOR_BY_TICKER[row.ticker] === featured.name)
    const representative = members.find((row) => row.ticker === featured.ticker) ?? members[0]
    const capture = median(members.map((row) => number(row.capture)))
    const mdd = median(members.map((row) => number(row.mddImprovement ?? row.mdd)))
    const passed = members.filter((row) => row.verdict === '기준 통과').length
    return {
      name: featured.name,
      representative: representative?.ticker ?? '—',
      count: members.length,
      capture: formatPercent(capture),
      mdd: formatPercent(mdd, '%p'),
      passed,
    }
  })
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

  const rows = (report.tickers ?? []).map((row) => {
    const capture = number(row.capture)
    const mdd = number(row.mddImprovement)
    const pass = capture !== null && capture >= 60 && mdd !== null && mdd >= 0
    return {
      ticker: row.ticker,
      sector: SECTOR_BY_TICKER[row.ticker] ?? '기타',
      buyHold: formatPercent(row.buyHoldReturn),
      action: formatPercent(row.actionReturn),
      capture: formatPercent(row.capture),
      mdd: formatPercent(row.mddImprovement, '%p'),
      actions: `${row.actions ?? 0}회`,
      verdict: pass ? '기준 통과' : '추가 검증',
      tone: pass ? 'pass' : 'watch',
    }
  })

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
    rows,
    featuredSectors: summarizeFeaturedSectors(rows),
  }
}
