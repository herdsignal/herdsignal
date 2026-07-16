package com.herdsignal.service;

import java.time.LocalDate;

/** 최근 실제 매수·매도 이후 동일 방향 행동을 제한하는 상태. */
public record ActionCooldownContext(
        Cooldown buy,
        Cooldown sell
) {
    public static ActionCooldownContext none() {
        return new ActionCooldownContext(Cooldown.none(), Cooldown.none());
    }

    public Cooldown forBuySide(boolean buySide) {
        return buySide ? buy : sell;
    }

    public record Cooldown(
            boolean active,
            int elapsedTradingDays,
            int remainingTradingDays,
            LocalDate lastActionDate
    ) {
        public static Cooldown none() {
            return new Cooldown(false, 0, 0, null);
        }
    }
}
