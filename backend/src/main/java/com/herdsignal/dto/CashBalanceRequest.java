package com.herdsignal.dto;

import lombok.Getter;

import java.math.BigDecimal;

/**
 * 현금 보유액 수정 요청 DTO.
 */
@Getter
public class CashBalanceRequest {

    /** 현금 보유액 (USD) */
    private BigDecimal cashAmount;
}
