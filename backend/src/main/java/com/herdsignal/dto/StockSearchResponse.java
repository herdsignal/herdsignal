package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

/**
 * 종목 심볼 검색 응답.
 */
@Getter
@Builder
public class StockSearchResponse {

    /** 원본 검색어 */
    private String query;

    /** 검색 후보 목록 */
    private List<StockSearchItem> results;
}
