package com.herdsignal.service.decision;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

/** SEC 원문 검수를 통과한 단일 경영진 가이던스 범위. 방향성 해석 권한은 없다. */
public record GuidanceEvidenceFactSnapshot(
        String bindingId,
        String ticker,
        String cik,
        String accessionNumber,
        OffsetDateTime acceptedAt,
        String sourceUrl,
        String sourceSha256,
        String sourceKind,
        String metric,
        String fiscalPeriod,
        String accountingBasis,
        String metricSubtype,
        String unit,
        BigDecimal lowerBound,
        BigDecimal upperBound,
        BigDecimal midpoint,
        String sourceVersion
) {
}
