package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

/**
 * HERD 히스토리 응답 DTO.
 * GET /api/stocks/{ticker}/herd/history 응답 본문.
 */
@Getter
@Builder
public class HerdHistoryResponse {

    /** 날짜 오름차순 정렬된 HERD 점수 목록 */
    private final List<HerdHistoryPoint> points;
}
