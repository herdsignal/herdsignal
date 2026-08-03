package com.herdsignal.service.decision;

import java.math.BigDecimal;
import java.time.LocalDate;

/** 저장 판단 이후 실제 가격 경로. 미도래 기간은 PENDING으로 남긴다. */
public record OperatingReviewOutcome(
        int horizonMonths,
        LocalDate targetDate,
        String status,
        LocalDate measuredAt,
        BigDecimal closePrice,
        BigDecimal priceReturnPct,
        BigDecimal policyDifferencePct
) {
}
