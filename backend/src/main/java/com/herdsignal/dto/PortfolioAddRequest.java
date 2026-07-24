package com.herdsignal.dto;

import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.NotBlank;
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
    @NotBlank(message = "티커는 필수입니다")
    @Pattern(regexp = "(?i)^[A-Z0-9.-]{1,10}$", message = "티커 형식이 올바르지 않습니다")
    private String ticker;

    /** 평균 매수가 (USD, 선택) */
    @Positive(message = "평균 매수가는 0보다 커야 합니다")
    private BigDecimal avgPrice;

    /** 보유 수량 (선택) */
    @Positive(message = "보유 수량은 0보다 커야 합니다")
    private BigDecimal quantity;
}
