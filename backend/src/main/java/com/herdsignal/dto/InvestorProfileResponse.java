package com.herdsignal.dto;

import com.herdsignal.domain.InvestorProfile;

import java.math.BigDecimal;

public record InvestorProfileResponse(
        String strategy,
        String riskTolerance,
        int timeHorizonYears,
        int liquidityBufferMonths,
        BigDecimal maxActionRatio,
        BigDecimal targetEquityRatio
) {
    public static InvestorProfileResponse from(InvestorProfile profile) {
        return new InvestorProfileResponse(
                profile.getStrategy(), profile.getRiskTolerance(), profile.getTimeHorizonYears(),
                profile.getLiquidityBufferMonths(), profile.getMaxActionRatio(),
                profile.getTargetEquityRatio()
        );
    }
}
