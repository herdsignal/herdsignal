package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * 포트폴리오 전체 요약 응답 DTO.
 * 집계 데이터(총액·수익률)와 종목별 상세 데이터를 함께 반환.
 *
 * 총액과 종목별 데이터 모두 user_portfolio + 동일 조회 기준의 daily_prices에서 계산한다.
 * portfolio_history는 과거 차트에만 사용한다.
 */
@Getter
@Builder
public class PortfolioSummaryResponse {

    /** 총 평가금액 (USD) */
    private BigDecimal totalValue;

    /** 현금 제외 주식 평가금액 (USD) */
    private BigDecimal investedValue;

    /** 현금 보유액 (USD) */
    private BigDecimal cashBalance;

    /** 주식 평가금액 + 현금 보유액 (USD) */
    private BigDecimal totalAssetValue;

    /** 총 매입금액 (USD) */
    private BigDecimal totalCost;

    /** 총 수익률 (%) */
    private BigDecimal totalReturnPct;

    /**
     * 포트폴리오 일일 등락률 (%).
     * 각 종목의 동일 조회 기준 일일 변동을 평가금액으로 가중한 변화율.
     */
    private BigDecimal dailyChangePct;

    /** 모든 보유 종목에 공통으로 확보된 가장 최근 거래일 (종목별 기준일 중 최솟값) */
    private LocalDate marketDataDate;

    /** 보유 종목별 평가 상세 목록 */
    private List<StockHoldingResponse> stocks;
}
