package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * GET /api/market/spy 응답 DTO.
 * Python market_collector.get_spy_market_data() 결과를 담는다.
 */
@Getter
@Builder
public class SpyMarketResponse {

    /** 티커 심볼 ("SPY") */
    private final String ticker;

    /** 최신 종가 (USD, 약 15분 지연) */
    private final Double currentPrice;

    /** 1개월 수익률 (%) */
    private final Double return1mPct;

    /** 종가 기준 날짜 (YYYY-MM-DD) */
    private final String priceDate;
}
