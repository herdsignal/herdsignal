const BLOCKER_LABELS = {
  PERSONAL_POLICY_PREHOLDOUT_FAILED: '사전 채택 기준 미통과',
  BLIND_HOLDOUT_NOT_PASSED: 'Blind holdout 미통과',
  SURVIVORSHIP_SAFE_FALSE: '생존자 편향 잔존',
  PERSONAL_MVP_PROMOTION_REPORT_UNAVAILABLE: '최신 판정 파일 없음',
  PERSONAL_MVP_PROMOTION_REPORT_INVALID: '최신 판정 파일 오류',
}

export function presentVNextStatus(status) {
  if (!status?.sourceContractAccepted) {
    return {
      sourceAccepted: false,
      observationLabel: '확인 불가',
      actionLabel: '차단',
      actionRatioLabel: '0%',
      holdoutLabel: '미개방',
      blockers: (status?.promotionBlockers ?? ['PERSONAL_MVP_PROMOTION_REPORT_UNAVAILABLE'])
        .map((blocker) => BLOCKER_LABELS[blocker] ?? blocker),
    }
  }

  return {
    sourceAccepted: true,
    observationLabel: status.validationStatus === 'STATE_OBSERVATION_MVP_READY'
      ? 'State S1'
      : '확인 필요',
    actionLabel: status.adoptableCandidate ? '검토 가능' : '후보 없음',
    actionRatioLabel: `${Number(status.operationalActionRatio ?? 0) * 100}%`,
    holdoutLabel: status.blindHoldoutOpened ? '개방됨' : '미개방',
    blockers: (status.promotionBlockers ?? [])
      .map((blocker) => BLOCKER_LABELS[blocker] ?? blocker),
  }
}
