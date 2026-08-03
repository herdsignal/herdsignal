package com.herdsignal.service.decision;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;

/** 시장 맥락 계산기에 전달하는 수정 종가 한 점. */
public record MarketSectorPricePoint(
        LocalDate date,
        BigDecimal close,
        OffsetDateTime observedAt
) {
}
