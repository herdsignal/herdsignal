package com.herdsignal.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

import java.math.BigDecimal;

/**
 * 현금 보유액 수정 요청 DTO.
 */
@Getter
public class CashBalanceRequest {

    /** 현금 보유액 (USD) */
    @NotNull(message = "현금 보유액은 필수입니다")
    @DecimalMin(value = "0.0", message = "현금 보유액은 0 이상이어야 합니다")
    private BigDecimal cashAmount;
}
