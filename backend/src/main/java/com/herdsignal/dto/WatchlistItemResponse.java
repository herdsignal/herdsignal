package com.herdsignal.dto;

import com.herdsignal.domain.UserWatchlist;

/** JPA 내부 식별자와 사용자 ID를 노출하지 않는 관심 종목 조회 계약. */
public record WatchlistItemResponse(String ticker, String memo) {
    public static WatchlistItemResponse from(UserWatchlist item) {
        return new WatchlistItemResponse(item.getTicker(), item.getMemo());
    }
}
