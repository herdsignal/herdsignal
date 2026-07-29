package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/** Daily D1과 주간 확정 S1의 단계 불일치. 행동·확정 사건 권한은 없다. */
public record ProvisionalObservationAttention(
        String ticker,
        String companyName,
        String trackingScope,
        LocalDate provisionalDate,
        BigDecimal provisionalScore,
        String provisionalStage,
        LocalDate confirmedDate,
        BigDecimal confirmedScore,
        String confirmedStage,
        String eventType
) {}
