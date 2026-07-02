package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * HERD 히스토리 단일 포인트 — 날짜 + 점수.
 * GET /api/stocks/{ticker}/herd/history 응답 내 points 배열 원소.
 */
@Getter
@Builder
public class HerdHistoryPoint {

    /** 점수 기준 날짜 (ISO 8601: "2023-07-01") */
    private final String date;

    /** HERD 점수 (0.0 ~ 100.0) */
    private final Double score;
}
