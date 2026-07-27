package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 같은 미국 시장 세션의 수정 종가와 S1 관찰값을 결합한 차트 지점.
 * 가격이 누락된 관찰은 폐기하지 않고 adjustedClose를 null로 보존한다.
 */
public record HerdPriceTimelinePoint(
        LocalDate observationDate,
        LocalDate marketSession,
        BigDecimal adjustedClose,
        BigDecimal herdScore,
        String herdStage,
        String transition,
        boolean transitionEvent
) {}
