package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

/**
 * 관심 종목 전체 HERD 조회 응답 DTO.
 * HERD 데이터가 없는 종목은 결과에서 제외된다 (Python 스케줄러 미실행 종목).
 */
@Getter
@Builder
public class WatchlistHerdResponse {

    /** HERD 데이터가 있는 관심 종목별 점수 + 지표 분해값 목록 */
    private List<HerdScoreResponse> stocks;

    /** HERD 데이터가 있는 종목 수 */
    private int totalCount;

    /** 정적 팩토리 메서드 */
    public static WatchlistHerdResponse of(List<HerdScoreResponse> stocks) {
        return WatchlistHerdResponse.builder()
                .stocks(stocks)
                .totalCount(stocks.size())
                .build();
    }
}
