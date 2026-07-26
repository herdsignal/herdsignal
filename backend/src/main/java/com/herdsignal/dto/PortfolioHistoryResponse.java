package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * 포트폴리오 히스토리 응답 DTO.
 * 날짜별 계좌 가치와 보유 주식 평가손익 시계열 데이터를 포함.
 * 계좌 가치 변화는 입출금·종목 추가/삭제 영향을 포함하므로 투자 성과가 아니다.
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

        /** 하위 호환용 계좌 가치 (주식 평가금액 + 현금, USD) */
        private BigDecimal totalValue;

        /** 현금 제외 주식 평가금액 (USD) */
        private BigDecimal investedValue;

        /** 현금 보유액 (USD) */
        private BigDecimal cashBalance;

        /** 주식 평가금액 + 현금 보유액 (USD) */
        private BigDecimal totalAssetValue;

        /** 해당 시점 보유 주식의 매입원가 대비 평가손익률 (%) */
        private BigDecimal totalReturnPct;
    }
}
