package com.herdsignal.service;

import com.herdsignal.repository.HerdScoreRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 포트폴리오/관심종목에 추가 가능한 티커인지 검증한다.
 * 검색 화면에서 HERD 계산이 완료된 종목만 저장 대상으로 허용해
 * 오타 티커가 백필·스케줄러 대상에 섞이지 않도록 막는다.
 */
@Service
@RequiredArgsConstructor
public class TickerReadinessService {

    private static final String TICKER_PATTERN = "^[A-Z][A-Z0-9.-]{0,9}$";

    private final HerdScoreRepository herdScoreRepository;

    @Transactional(readOnly = true)
    public String normalizeAndValidate(String rawTicker) {
        if (rawTicker == null || rawTicker.trim().isEmpty()) {
            throw new IllegalArgumentException("티커를 입력해주세요.");
        }

        String ticker = rawTicker.trim().toUpperCase();
        if (!ticker.matches(TICKER_PATTERN)) {
            throw new IllegalArgumentException("올바른 미국 주식 티커 형식이 아닙니다.");
        }

        boolean hasHerdScore = herdScoreRepository.findTopByTickerOrderByScoreDateDesc(ticker).isPresent();
        if (!hasHerdScore) {
            throw new IllegalArgumentException(
                    "HERD 데이터가 준비된 종목만 추가할 수 있습니다. 검색에서 HERD 계산 후 다시 시도해주세요.");
        }

        return ticker;
    }
}
