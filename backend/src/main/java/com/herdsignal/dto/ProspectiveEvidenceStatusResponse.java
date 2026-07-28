package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/** 가격 결과를 미리 보지 않고 쌓는 State S1 전향 관찰 원장의 읽기 전용 상태. */
public record ProspectiveEvidenceStatusResponse(
        String status,
        boolean auditPassed,
        int observationArchives,
        LocalDate firstObservationDate,
        LocalDate latestObservationDate,
        int observationRecords,
        int maturedOutcomes,
        int pendingOutcomes,
        String operationalAction,
        BigDecimal operationalActionRatio
) {
}
