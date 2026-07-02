package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 일별 종가 단일 포인트.
 * GET /api/stocks/{ticker}/prices 응답 내 points 배열 원소.
 */
@Getter
@Builder
public class PricePoint {

    /** 거래일 (ISO 8601: "2024-07-01") */
    private final String date;

    /** 수정 종가 */
    private final Double close;
}
