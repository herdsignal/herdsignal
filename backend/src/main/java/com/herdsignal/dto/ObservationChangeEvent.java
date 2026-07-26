package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/** 행동 해석이 없는 State S1 관찰 변화 한 건. */
public record ObservationChangeEvent(
        String id,
        String ticker,
        String companyName,
        String sector,
        String logoUrl,
        LocalDate observationDate,
        String eventType,
        BigDecimal stateScore,
        String stage,
        String previousStage,
        String transition,
        BigDecimal delta4w,
        boolean unread
) {}
