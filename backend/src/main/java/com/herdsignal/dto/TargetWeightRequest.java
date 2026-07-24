package com.herdsignal.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;

public record TargetWeightRequest(
        @NotNull(message = "목표 비중은 필수입니다")
        @DecimalMin(value = "0.0", message = "목표 비중은 0% 이상이어야 합니다")
        @DecimalMax(value = "1.0", message = "목표 비중은 100% 이하여야 합니다")
        BigDecimal targetWeight
) {
}
