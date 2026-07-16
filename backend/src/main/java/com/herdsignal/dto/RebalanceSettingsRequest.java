package com.herdsignal.dto;

import java.math.BigDecimal;

public record RebalanceSettingsRequest(
        BigDecimal budget,
        BigDecimal cashTargetRatio,
        String mode
) {
}
