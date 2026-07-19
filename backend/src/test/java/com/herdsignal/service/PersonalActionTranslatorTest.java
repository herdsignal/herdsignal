package com.herdsignal.service;

import com.herdsignal.domain.InvestorProfile;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class PersonalActionTranslatorTest {

    private final PersonalActionTranslator translator = new PersonalActionTranslator();

    @Test
    void personalProfileOnlyCapsMarketRatio() {
        var conservative = translator.translate(
                0.20, "시장 행동", profile("EXISTING_HOLDER", "CONSERVATIVE", 10, 6), true, 10);
        var growth = translator.translate(
                0.20, "시장 행동", profile("EXISTING_HOLDER", "GROWTH", 10, 6), true, 10);

        assertThat(conservative.ratio()).isEqualTo(0.08);
        assertThat(growth.ratio()).isEqualTo(0.20);
        assertThat(conservative.label()).isEqualTo("시장 행동");
        assertThat(growth.label()).isEqualTo("시장 행동");
    }

    @Test
    void lowLiquidityBlocksBuyWithoutChangingHerdInput() {
        var result = translator.translate(
                0.20, "분할 매수", profile("NEW_ENTRY", "GROWTH", 10, 2), false, 12);

        assertThat(result.ratio()).isZero();
        assertThat(result.label()).isEqualTo("현금 여유 확보 우선");
        assertThat(result.warnings()).anyMatch(value -> value.contains("생활비 여유"));
    }

    private InvestorProfile profile(
            String strategy,
            String risk,
            int horizon,
            int liquidity
    ) {
        return InvestorProfile.builder()
                .strategy(strategy)
                .riskTolerance(risk)
                .timeHorizonYears(horizon)
                .liquidityBufferMonths(liquidity)
                .maxActionRatio(new BigDecimal("0.30"))
                .targetEquityRatio(new BigDecimal("0.70"))
                .build();
    }
}
