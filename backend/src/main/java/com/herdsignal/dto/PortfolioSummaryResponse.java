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
 * 총액 데이터 출처: portfolio_history 최신 스냅샷 (Python 스케줄러가 매일 갱신)
 * 종목별 데이터 출처: user_portfolio + daily_prices 현재가 실시간 조합
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
     * portfolio_history 최신 2개 스냅샷의 total_value 변화율.
     * 스냅샷이 1개뿐이면 0.0.
     */
    private BigDecimal dailyChangePct;

    /** 모든 보유 종목에 공통으로 확보된 가장 최근 거래일 (종목별 기준일 중 최솟값) */
    private LocalDate marketDataDate;

    /** 보유 종목별 평가 상세 목록 */
    private List<StockHoldingResponse> stocks;
}
