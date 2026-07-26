package com.herdsignal.service;

import org.springframework.stereotype.Component;

import java.util.Locale;

/**
 * 사용자 자산·관심종목에 저장할 미국 종목 심볼의 형식 경계.
 *
 * <p>HERD 관찰값 존재 여부는 사용자 보유 사실과 무관하므로 여기서 검사하지
 * 않는다. 관찰값이 없는 심볼은 저장 후 스케줄러가 수집을 시도하며, 화면에서는
 * 준비 중으로 표시한다.</p>
 */
@Component
public class TickerSymbolPolicy {

    private static final String TICKER_PATTERN = "^[A-Z][A-Z0-9.-]{0,9}$";

    public String normalize(String rawTicker) {
        if (rawTicker == null || rawTicker.trim().isEmpty()) {
            throw new IllegalArgumentException("티커를 입력해주세요.");
        }

        String ticker = rawTicker.trim().toUpperCase(Locale.ROOT);
        if (!ticker.matches(TICKER_PATTERN)) {
            throw new IllegalArgumentException("올바른 미국 주식 티커 형식이 아닙니다.");
        }
        return ticker;
    }
}
