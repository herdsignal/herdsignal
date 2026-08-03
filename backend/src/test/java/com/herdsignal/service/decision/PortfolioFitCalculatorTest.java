package com.herdsignal.service.decision;

import com.herdsignal.service.PortfolioActionContext;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class PortfolioFitCalculatorTest {
    private final PortfolioFitCalculator calculator = new PortfolioFitCalculator();

    @Test
    void exposesRawPortfolioRatiosWithoutInventingATickerTarget() {
        PortfolioFitAssessment result = calculator.assess(
                new PortfolioActionContext(true, 0.20, 0.75, 0.70));

        assertThat(result.status()).isEqualTo(AssessmentStatus.AVAILABLE);
        assertThat(result.currentTickerWeight()).isEqualTo(0.20);
        assertThat(result.currentCashRatio()).isEqualTo(0.25);
        assertThat(result.equityTargetGap()).isCloseTo(0.05, within(0.000001));
        assertThat(result.limitation()).contains("개별 종목 목표 비중이 없으므로");
    }

    @Test
    void failsClosedWhenPortfolioInputsAreUnavailable() {
        PortfolioFitAssessment result = calculator.assess(PortfolioActionContext.unavailable());

        assertThat(result.status()).isEqualTo(AssessmentStatus.NO_VIEW);
        assertThat(result.portfolioAvailable()).isFalse();
        assertThat(result.currentCashRatio()).isZero();
        assertThat(result.equityTargetGap()).isZero();
    }

    private org.assertj.core.data.Offset<Double> within(double value) {
        return org.assertj.core.data.Offset.offset(value);
    }
}
