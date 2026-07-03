package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 종목 검색 후보 1건.
 */
@Getter
@Builder
public class StockSearchItem {

    /** 거래 가능한 티커 심볼 */
    private String ticker;

    /** 회사명 또는 상품명 */
    private String name;

    /** Finnhub 심볼 타입 */
    private String type;

    /** 표시용 심볼 */
    private String displaySymbol;
}
