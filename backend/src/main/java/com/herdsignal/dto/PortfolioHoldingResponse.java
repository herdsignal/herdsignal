package com.herdsignal.dto;

import com.herdsignal.domain.UserPortfolio;

import java.math.BigDecimal;

/** JPA 내부 식별자와 사용자 ID를 노출하지 않는 보유 종목 조회 계약. */
public record PortfolioHoldingResponse(
        String ticker,
        BigDecimal avgPrice,
        BigDecimal quantity,
        BigDecimal targetWeight,
        String memo
) {
    public static PortfolioHoldingResponse from(UserPortfolio holding) {
        return new PortfolioHoldingResponse(
                holding.getTicker(),
                holding.getAvgPrice(),
                holding.getQuantity(),
                holding.getTargetWeight(),
                holding.getMemo()
        );
    }
}
