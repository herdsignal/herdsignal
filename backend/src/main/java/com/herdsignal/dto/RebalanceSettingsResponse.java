package com.herdsignal.dto;

import com.herdsignal.domain.InvestorProfile;

import java.math.BigDecimal;

public record RebalanceSettingsResponse(
        BigDecimal budget,
        BigDecimal cashTargetRatio,
        String mode
) {
    public static RebalanceSettingsResponse from(InvestorProfile profile) {
        return new RebalanceSettingsResponse(
                profile.getRebalanceBudget(),
                profile.getCashTargetRatio(),
                profile.getRebalanceMode()
        );
    }
}
