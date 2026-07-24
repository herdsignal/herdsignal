package com.herdsignal.service;

import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;

/**
 * 미국 정규장 기준으로 포트폴리오 스냅샷에 사용할 거래일을 계산한다.
 *
 * <p>시간 판단을 포트폴리오 서비스들에서 분리해 동일한 세션 규칙을 공유한다.</p>
 */
@Component
public class UsMarketSessionClock {

    static final ZoneId KST_ZONE = ZoneId.of("Asia/Seoul");
    static final LocalTime US_MARKET_DAY_START_KST = LocalTime.of(22, 30);

    private final Clock clock;

    public UsMarketSessionClock() {
        this(Clock.system(KST_ZONE));
    }

    UsMarketSessionClock(Clock clock) {
        this.clock = clock;
    }

    public LocalDate currentSessionDate() {
        LocalDate today = LocalDate.now(clock);
        LocalTime now = LocalTime.now(clock);
        return now.isBefore(US_MARKET_DAY_START_KST) ? today.minusDays(1) : today;
    }
}
