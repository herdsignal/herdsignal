package com.herdsignal.service;

import java.time.LocalDate;

/** 화면에서 허용하는 HERD 히스토리 기간만 날짜 범위로 변환한다. */
final class HerdHistoryPeriod {

    private HerdHistoryPeriod() {
    }

    static LocalDate cutoff(String period, LocalDate today) {
        if (period == null) return today.minusYears(3);
        return switch (period.trim().toLowerCase()) {
            case "1m" -> today.minusMonths(1);
            case "3m" -> today.minusMonths(3);
            case "6m" -> today.minusMonths(6);
            case "1y" -> today.minusYears(1);
            case "3y" -> today.minusYears(3);
            default -> today.minusYears(3);
        };
    }
}
