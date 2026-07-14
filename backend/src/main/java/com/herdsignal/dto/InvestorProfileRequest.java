package com.herdsignal.dto;

import java.math.BigDecimal;

public record InvestorProfileRequest(
        String strategy,
        String riskTolerance,
        Integer timeHorizonYears,
        Integer liquidityBufferMonths,
        BigDecimal maxActionRatio,
        BigDecimal targetEquityRatio
) {}
