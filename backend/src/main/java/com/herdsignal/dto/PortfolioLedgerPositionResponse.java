package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;

@Getter
@Builder
public class PortfolioLedgerPositionResponse {

    private String ticker;
    private BigDecimal quantity;
    private BigDecimal averageCost;
    private BigDecimal costBasis;
    private BigDecimal latestPrice;
    private LocalDate priceDate;
    private BigDecimal marketValue;
    private BigDecimal realizedPnl;
    private BigDecimal unrealizedPnl;
    private BigDecimal unrealizedReturnPct;
    private boolean priceAvailable;
}
