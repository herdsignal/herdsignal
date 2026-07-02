package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

/**
 * 내부자 거래 응답 DTO.
 * GET /api/stocks/{ticker}/insider 응답 본문.
 */
@Getter
@Builder
public class InsiderResponse {

    /** 최신순 내부자 거래 목록 (최대 10건) */
    private final List<InsiderTransaction> transactions;
}
