package com.herdsignal.service.decision;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/** 출처와 관측시점을 잃지 않는 장기 운용 판단의 최소 사실 단위. */
public record EvidenceFact(
        String id,
        DecisionArea area,
        String label,
        String value,
        LocalDate asOfDate,
        OffsetDateTime observedAt,
        String source,
        String sourceVersion,
        String assetType,
        EvidenceQuality quality,
        boolean requiredForDecision,
        boolean pointInTimeRequired,
        boolean pointInTimeValid,
        Integer maximumAgeDays
) {
}
