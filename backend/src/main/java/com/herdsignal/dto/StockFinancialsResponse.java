package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * GET /api/stocks/{ticker}/financials 응답 DTO.
 * Python stock_info_collector.get_stock_financials() 결과를 담는다.
 * 데이터가 없는 종목의 경우 수치 필드가 null일 수 있다.
 */
@Getter
@Builder
public class StockFinancialsResponse {

    /** 티커 심볼 */
    private final String ticker;

    /** 시가총액 (USD) */
    private final Double marketCap;

    /** PER — Price/Earnings (TTM) */
    private final Double trailingPe;

    /** EPS (TTM, USD) */
    private final Double eps;

    /** 영업이익률 (%) */
    private final Double operatingMargin;

    /** 매출 (TTM, USD) */
    private final Double totalRevenue;

    /** 배당수익률 (%) */
    private final Double dividendYield;
}
