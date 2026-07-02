package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 내부자 거래 단건 DTO.
 * GET /api/stocks/{ticker}/insider 응답 내 transactions 배열 원소.
 */
@Getter
@Builder
public class InsiderTransaction {

    /** 내부자 이름 */
    private final String name;

    /** 거래 코드 — "P"=매수(Purchase), "S"=매도(Sale) */
    private final String transactionCode;

    /** 거래 주수 */
    private final Long share;

    /** 거래일 (ISO 8601: "2024-07-01") */
    private final String date;
}
