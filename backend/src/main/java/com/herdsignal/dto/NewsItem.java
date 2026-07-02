package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 뉴스 단건 DTO.
 * GET /api/stocks/{ticker}/news 응답 내 news 배열 원소.
 */
@Getter
@Builder
public class NewsItem {

    /** 뉴스 제목 */
    private final String headline;

    /** 출처 (예: "CNBC") */
    private final String source;

    /** 원문 URL */
    private final String url;

    /** 기사 날짜 (ISO 8601: "2024-07-01") */
    private final String date;
}
