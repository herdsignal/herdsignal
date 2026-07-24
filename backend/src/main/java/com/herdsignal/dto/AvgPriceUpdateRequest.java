package com.herdsignal.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 평균 매수가·수량 수정 요청 DTO.
 * PATCH /api/portfolio/{ticker}/avg-price 에서 사용.
 * avgPrice와 quantity 모두 필수.
 */
@Getter
@NoArgsConstructor
public class AvgPriceUpdateRequest {

    /** 수정할 평균 매수가 (USD) */
    @NotNull(message = "평균 매수가는 필수입니다")
    @Positive(message = "평균 매수가는 0보다 커야 합니다")
    private BigDecimal avgPrice;

    /** 수정할 보유 수량 */
    @NotNull(message = "보유 수량은 필수입니다")
    @Positive(message = "보유 수량은 0보다 커야 합니다")
    private BigDecimal quantity;
}
