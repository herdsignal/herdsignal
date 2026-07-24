package com.herdsignal.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

import java.math.BigDecimal;

public record InvestorProfileRequest(
        @NotBlank(message = "투자 방식은 필수입니다")
        @Pattern(
                regexp = "EXISTING_HOLDER|NEW_ENTRY|MONTHLY_DCA|TARGET_REBALANCE",
                message = "지원하지 않는 투자 방식입니다")
        String strategy,
        @NotBlank(message = "위험 허용도는 필수입니다")
        @Pattern(
                regexp = "CONSERVATIVE|BALANCED|GROWTH",
                message = "지원하지 않는 위험 허용도입니다")
        String riskTolerance,
        @Min(value = 1, message = "투자 기간은 1년 이상이어야 합니다")
        @Max(value = 50, message = "투자 기간은 50년 이하여야 합니다")
        Integer timeHorizonYears,
        @Min(value = 0, message = "생활비 여유는 0개월 이상이어야 합니다")
        @Max(value = 60, message = "생활비 여유는 60개월 이하여야 합니다")
        Integer liquidityBufferMonths,
        @DecimalMin(value = "0.01", message = "1회 최대 행동비율은 1% 이상이어야 합니다")
        @DecimalMax(value = "0.30", message = "1회 최대 행동비율은 30% 이하여야 합니다")
        BigDecimal maxActionRatio,
        @DecimalMin(value = "0.10", message = "목표 주식비중은 10% 이상이어야 합니다")
        @DecimalMax(value = "1.00", message = "목표 주식비중은 100% 이하여야 합니다")
        BigDecimal targetEquityRatio
) {}
