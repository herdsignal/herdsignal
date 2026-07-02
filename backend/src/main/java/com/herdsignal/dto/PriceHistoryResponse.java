package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

/**
 * 종목 가격 히스토리 응답 DTO.
 * GET /api/stocks/{ticker}/prices?period=1M|3M|1Y|5Y 응답 본문.
 */
@Getter
@Builder
public class PriceHistoryResponse {

    /** 날짜 오름차순 정렬된 일별 종가 목록 */
    private final List<PricePoint> points;
}
