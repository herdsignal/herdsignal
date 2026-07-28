package com.herdsignal.dto;

import java.math.BigDecimal;
import java.util.List;

public record PortfolioSourceReconciliationResponse(
        String status,
        boolean ledgerManaged,
        boolean ledgerCanBecomeSource,
        BigDecimal manualCash,
        BigDecimal ledgerCash,
        BigDecimal cashDifference,
        List<PositionDifference> positionDifferences,
        List<String> errors
) {
    public record PositionDifference(
            String ticker,
            BigDecimal manualQuantity,
            BigDecimal ledgerQuantity,
            BigDecimal quantityDifference
    ) {}
}
