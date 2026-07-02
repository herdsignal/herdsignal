package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

/**
 * 뉴스 응답 DTO.
 * GET /api/stocks/{ticker}/news 응답 본문.
 */
@Getter
@Builder
public class NewsResponse {

    /** 최신순 뉴스 목록 (최대 5건) */
    private final List<NewsItem> news;
}
