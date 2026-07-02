package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 애널리스트 컨센서스 응답 DTO.
 * GET /api/stocks/{ticker}/analyst 응답 본문.
 * Finnhub recommendation_trends 최신 1개월 데이터 기반.
 */
@Getter
@Builder
public class AnalystResponse {

    /** Strong Buy 추천 수 */
    private final Integer strongBuy;

    /** Buy 추천 수 */
    private final Integer buy;

    /** Hold 추천 수 */
    private final Integer hold;

    /** Sell 추천 수 */
    private final Integer sell;

    /** Strong Sell 추천 수 */
    private final Integer strongSell;

    /** 전체 애널리스트 수 */
    private final Integer total;

    /** 컨센서스 문자열 (예: "Strong Buy", "Buy", "Hold", "Sell") */
    private final String consensus;

    /** 데이터 기준 연월 (예: "2024-07-01") */
    private final String period;
}
