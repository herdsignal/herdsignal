package com.herdsignal.service;

import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;

/**
 * 미국 정규장 기준으로 포트폴리오 스냅샷에 사용할 거래일을 계산한다.
 *
 * <p>시간 판단을 포트폴리오 서비스들에서 분리해 동일한 세션 규칙을 공유한다.</p>
 */
@Component
public class UsMarketSessionClock {

    static final ZoneId MARKET_ZONE = ZoneId.of("America/New_York");
    static final LocalTime REGULAR_MARKET_CLOSE = LocalTime.of(16, 0);

    private final Clock clock;

    public UsMarketSessionClock() {
        this(Clock.systemUTC());
    }

    UsMarketSessionClock(Clock clock) {
        this.clock = clock;
    }

    public LocalDate currentSessionDate() {
        ZonedDateTime marketNow = ZonedDateTime.now(clock).withZoneSameInstant(MARKET_ZONE);
        LocalDate candidate = marketNow.toLocalTime().isBefore(REGULAR_MARKET_CLOSE)
                ? marketNow.toLocalDate().minusDays(1)
                : marketNow.toLocalDate();
        while (candidate.getDayOfWeek().getValue() >= 6) {
            candidate = candidate.minusDays(1);
        }
        return candidate;
    }
}
