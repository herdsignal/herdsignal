package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 현금 보유액 응답 DTO.
 */
@Getter
@Builder
public class CashBalanceResponse {

    /** 현금 보유액 (USD) */
    private BigDecimal cashAmount;

    /** 현금 스냅샷 기준일 */
    private LocalDate snapshotDate;
}
