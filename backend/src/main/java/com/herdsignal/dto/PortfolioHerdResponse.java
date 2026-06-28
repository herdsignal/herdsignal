package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

/**
 * 포트폴리오 전체 HERD 조회 응답 DTO.
 * 보유 종목별 HERD 점수 목록 + 평균 점수 + 종목 수를 함께 반환.
 */
@Getter
@Builder
public class PortfolioHerdResponse {

    /** 보유 종목별 HERD 점수 + 지표 분해값 목록 */
    private List<HerdScoreResponse> stocks;

    /** 포트폴리오 평균 HERD 점수 (소수점 2자리) */
    private Double averageScore;

    /** 조회된 종목 수 */
    private int totalCount;

    /**
     * 정적 팩토리 메서드.
     * 평균 점수는 herdScore가 null이 아닌 종목만으로 계산.
     */
    public static PortfolioHerdResponse of(List<HerdScoreResponse> stocks) {
        double avg = stocks.stream()
                .filter(s -> s.getHerdScore() != null)
                .mapToDouble(s -> s.getHerdScore().doubleValue())
                .average()
                .orElse(0.0);

        // 소수점 2자리 반올림
        double roundedAvg = Math.round(avg * 100.0) / 100.0;

        return PortfolioHerdResponse.builder()
                .stocks(stocks)
                .averageScore(roundedAvg)
                .totalCount(stocks.size())
                .build();
    }
}
