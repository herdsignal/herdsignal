package com.herdsignal.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 포트폴리오 종목 추가 요청 DTO.
 * ticker는 필수, avgPrice / quantity는 선택.
 */
@Getter
@NoArgsConstructor
public class PortfolioAddRequest {

    /** 티커 심볼 (필수) — Service에서 대문자로 정규화 */
    private String ticker;

    /** 평균 매수가 (USD, 선택) */
    private BigDecimal avgPrice;

    /** 보유 수량 (선택) */
    private BigDecimal quantity;
}
