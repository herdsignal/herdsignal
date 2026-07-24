package com.herdsignal.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

import java.math.BigDecimal;

public record RebalanceSettingsRequest(
        @NotNull(message = "리밸런싱 예산은 필수입니다")
        @DecimalMin(value = "0.0", message = "리밸런싱 예산은 0 이상이어야 합니다")
        BigDecimal budget,
        @NotNull(message = "현금 목표 비중은 필수입니다")
        @DecimalMin(value = "0.0", message = "현금 목표 비중은 0% 이상이어야 합니다")
        @DecimalMax(value = "1.0", message = "현금 목표 비중은 100% 이하여야 합니다")
        BigDecimal cashTargetRatio,
        @NotBlank(message = "리밸런싱 모드는 필수입니다")
        @Pattern(
                regexp = "CONSERVATIVE|STANDARD|AGGRESSIVE",
                message = "지원하지 않는 리밸런싱 모드입니다")
        String mode
) {
}
