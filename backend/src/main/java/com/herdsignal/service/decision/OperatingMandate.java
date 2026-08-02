package com.herdsignal.service.decision;

import com.herdsignal.domain.InvestorProfile;

import java.math.BigDecimal;

/** 사용자 설정과 연구 안전장치를 분리해 보여주는 장기 운용 계약. */
public record OperatingMandate(
        String strategy,
        String riskTolerance,
        int timeHorizonYears,
        int liquidityBufferMonths,
        BigDecimal userMaximumActionRatio,
        BigDecimal targetEquityRatio,
        int policyMaximumActionsPerYear,
        int policyMinimumActionIntervalDays,
        boolean leverageAllowed,
        BigDecimal effectiveActionRatioCap
) {
    private static final int MAXIMUM_ACTIONS_PER_YEAR = 5;
    private static final int MINIMUM_ACTION_INTERVAL_DAYS = 30;

    public static OperatingMandate from(InvestorProfile profile) {
        return new OperatingMandate(
                profile.getStrategy(),
                profile.getRiskTolerance(),
                profile.getTimeHorizonYears(),
                profile.getLiquidityBufferMonths(),
                profile.getMaxActionRatio(),
                profile.getTargetEquityRatio(),
                MAXIMUM_ACTIONS_PER_YEAR,
                MINIMUM_ACTION_INTERVAL_DAYS,
                false,
                BigDecimal.ZERO
        );
    }
}
