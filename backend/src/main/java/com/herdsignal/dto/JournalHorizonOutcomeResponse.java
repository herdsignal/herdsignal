package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 판단 기록 시점의 종가와 고정된 달력 기간 뒤 종가를 단순 비교한다.
 * 행동 방향의 성공·실패나 초과수익으로 해석하지 않는다.
 */
@Getter
@Builder
public class JournalHorizonOutcomeResponse {

    private String horizon;
    private LocalDate targetDate;
    private String status;
    private LocalDate priceDate;
    private BigDecimal closePrice;
    private BigDecimal returnPct;
}
