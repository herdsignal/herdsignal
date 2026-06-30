package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;

/**
 * 보유 종목 1개의 평가 정보 응답 DTO.
 * PortfolioSummaryResponse.stocks 리스트의 원소로 사용.
 */
@Getter
@Builder
public class StockHoldingResponse {

    /** 티커 심볼 */
    private String ticker;

    /** 평균 매수가 (USD) */
    private BigDecimal avgPrice;

    /** 보유 수량 */
    private BigDecimal quantity;

    /** 현재가 (daily_prices 최신 종가) */
    private BigDecimal currentPrice;

    /** 평가금액 = 현재가 × 수량 */
    private BigDecimal marketValue;

    /** 종목 수익률 (%) = (현재가 - 평균매수가) / 평균매수가 × 100 */
    private BigDecimal returnPct;

    /** 일일 등락률 (%) = (오늘 종가 - 전일 종가) / 전일 종가 × 100 */
    private BigDecimal dailyChangePct;
}
