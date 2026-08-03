package com.herdsignal.service.decision;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;

/** SEC 접수시각 기준으로 복원한 기업 재무 사실. 행동 분류값은 포함하지 않는다. */
public record BusinessEvidenceSnapshot(
        String ticker,
        String cik,
        LocalDate featureMonthEnd,
        String corpusStatus,
        OffsetDateTime latestFactAcceptedAt,
        String entityType,
        String sourceVersion,
        BigDecimal revenueYoy,
        BigDecimal netMargin,
        BigDecimal netMarginYoyChange,
        BigDecimal operatingCashFlowYoy,
        BigDecimal operatingCashFlowValue,
        BigDecimal liabilitiesToAssets,
        BigDecimal liabilitiesToAssetsYoyChange
) {
    public boolean usablePointInTimeFacts() {
        return "PIT_FACTS_READY".equals(corpusStatus)
                && "GENERAL".equals(entityType)
                && latestFactAcceptedAt != null;
    }
}
