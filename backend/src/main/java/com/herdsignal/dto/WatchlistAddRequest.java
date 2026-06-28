package com.herdsignal.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 관심 종목 추가 요청 DTO.
 * ticker는 필수, memo는 선택.
 */
@Getter
@NoArgsConstructor
public class WatchlistAddRequest {

    /** 티커 심볼 (필수) — Service에서 대문자로 정규화 */
    private String ticker;

    /** 메모 (선택) */
    private String memo;
}
