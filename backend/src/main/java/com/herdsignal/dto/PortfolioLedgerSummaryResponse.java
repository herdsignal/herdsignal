package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

@Getter
@Builder
public class PortfolioLedgerSummaryResponse {

    private String status;
    private String currency;
    private LocalDate priceAsOf;
    private boolean pricingComplete;
    private BigDecimal cashBalance;
    private BigDecimal marketValue;
    private BigDecimal accountValue;
    private BigDecimal costBasis;
    private BigDecimal realizedPnl;
    private BigDecimal unrealizedPnl;
    private BigDecimal dividends;
    private BigDecimal fees;
    private BigDecimal netContributions;
    private List<PortfolioLedgerPositionResponse> positions;
    private List<String> warnings;
    private List<String> errors;
}
