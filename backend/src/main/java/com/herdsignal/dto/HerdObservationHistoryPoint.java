package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/** 차트와 전환 이력에 필요한 최소 S1 관찰 지점. */
public record HerdObservationHistoryPoint(
        LocalDate observationDate,
        LocalDate lastObservedSession,
        BigDecimal stateScore,
        String stage,
        String transition,
        boolean transitionEvent
) {}
