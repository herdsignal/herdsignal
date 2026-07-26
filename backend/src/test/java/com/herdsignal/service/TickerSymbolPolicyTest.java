package com.herdsignal.service;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TickerSymbolPolicyTest {

    private final TickerSymbolPolicy policy = new TickerSymbolPolicy();

    @Test
    void normalizesTickerWithoutRequiringExistingHerdObservation() {
        assertThat(policy.normalize("  rklb  ")).isEqualTo("RKLB");
        assertThat(policy.normalize("brk-b")).isEqualTo("BRK-B");
    }

    @Test
    void rejectsBlankOrMalformedTicker() {
        assertThatThrownBy(() -> policy.normalize(" "))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> policy.normalize("AAPL!"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> policy.normalize("1AAPL"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
