package com.herdsignal.dto;

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
    private BigDecimal avgPrice;

    /** 수정할 보유 수량 */
    private BigDecimal quantity;
}
