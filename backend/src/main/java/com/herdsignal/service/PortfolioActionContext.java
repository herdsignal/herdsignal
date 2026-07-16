package com.herdsignal.service;

/** Action Layer가 사용할 실제 포트폴리오 비중 정보. */
public record PortfolioActionContext(
        boolean available,
        double currentTickerWeight,
        double currentEquityRatio,
        double targetEquityRatio
) {
    public static PortfolioActionContext unavailable() {
        return new PortfolioActionContext(false, 0.0, 0.0, 0.0);
    }
}
