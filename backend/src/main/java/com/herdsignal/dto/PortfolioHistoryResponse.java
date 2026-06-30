package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * 포트폴리오 히스토리 응답 DTO.
 * 날짜별 총 평가금액·수익률 시계열 데이터를 포함.
 * 프론트엔드 차트 렌더링에 사용.
 */
@Getter
@Builder
public class PortfolioHistoryResponse {

    /** 날짜별 히스토리 포인트 목록 (오래된 순) */
    private List<HistoryPoint> points;

    /**
     * 포트폴리오 히스토리 단일 포인트.
     * portfolio_history 테이블의 1개 행에 대응.
     */
    @Getter
    @Builder
    public static class HistoryPoint {

        /** 스냅샷 기준일 */
        private LocalDate date;

        /** 총 평가금액 (USD) */
        private BigDecimal totalValue;

        /** 총 수익률 (%) */
        private BigDecimal totalReturnPct;
    }
}
