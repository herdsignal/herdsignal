import { describe, expect, it } from 'vitest'
import { presentProspectiveEvidence } from './prospectiveEvidencePresentation'

describe('prospective evidence presentation', () => {
  it('shows audited observation accumulation without action claims', () => {
    expect(presentProspectiveEvidence({
      auditPassed: true,
      observationArchives: 1,
      firstObservationDate: '2026-07-24',
      latestObservationDate: '2026-07-24',
      observationRecords: 440,
      maturedOutcomes: 0,
      pendingOutcomes: 1320,
    })).toMatchObject({
      statusLabel: '수집 중',
      archives: '1회',
      records: '440개',
      matured: '0개',
      pending: '1,320개',
    })
  })

  it('fails closed when the audit is unavailable', () => {
    expect(presentProspectiveEvidence(null)).toMatchObject({
      available: false,
      statusLabel: '감사 확인 불가',
    })
  })
})
