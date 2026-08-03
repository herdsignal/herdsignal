package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class EvidenceGateTest {
    private final EvidenceGate gate = new EvidenceGate();
    private final OffsetDateTime generatedAt = OffsetDateTime.of(
            2026, 8, 3, 12, 0, 0, 0, ZoneOffset.UTC);

    @Test
    void opensForCompleteTimeValidPacket() {
        EvidenceGateResult result = gate.evaluate(packet(fact(
                "OBS.STATE", EvidenceQuality.AVAILABLE, true, true,
                LocalDate.of(2026, 8, 1), generatedAt.minusDays(2), 7)));

        assertThat(result.open()).isTrue();
        assertThat(result.reasons()).isEmpty();
    }

    @Test
    void blocksMissingRequiredFactAndPitViolation() {
        EvidenceGateResult result = gate.evaluate(packet(fact(
                "SEC.CASH_FLOW", EvidenceQuality.MISSING, true, false,
                LocalDate.of(2026, 7, 31), generatedAt.minusDays(3), 120)));

        assertThat(result.open()).isFalse();
        assertThat(result.reasons()).contains(
                "SEC.CASH_FLOW:REQUIRED_FACT_UNAVAILABLE",
                "SEC.CASH_FLOW:PIT_INVALID");
    }

    @Test
    void blocksDuplicateFutureAndStaleFacts() {
        EvidenceFact stale = fact(
                "OBS.STATE", EvidenceQuality.AVAILABLE, true, true,
                LocalDate.of(2026, 7, 1), generatedAt.minusDays(1), 7);
        EvidenceFact future = fact(
                "OBS.STATE", EvidenceQuality.AVAILABLE, true, true,
                LocalDate.of(2026, 8, 4), generatedAt.plusMinutes(1), 7);

        EvidenceGateResult result = gate.evaluate(packet(stale, future));

        assertThat(result.reasons()).contains(
                "OBS.STATE:ID_DUPLICATED",
                "OBS.STATE:STALE_BY_AGE",
                "OBS.STATE:FUTURE_AS_OF_DATE",
                "OBS.STATE:FUTURE_OBSERVED_AT");
    }

    @Test
    void permitsOptionalNoViewFact() {
        EvidenceFact noView = fact(
                "FLOW.SHORT_INTEREST", EvidenceQuality.NO_VIEW, false, true,
                LocalDate.of(2026, 8, 1), generatedAt.minusDays(2), 30);

        assertThat(gate.evaluate(packet(noView)).open()).isTrue();
    }

    @Test
    void blocksHerdObservationFromMasqueradingAsIndependentMarketEvidence() {
        EvidenceFact duplicate = new EvidenceFact(
                "OBS.SECTOR_REFERENCE", DecisionArea.MARKET_SECTOR, "참조 ETF", "SMH",
                LocalDate.of(2026, 8, 1), generatedAt.minusDays(2),
                "HERD_OBSERVATION", "HERD_STATE_S1", "COMMON_STOCK",
                EvidenceQuality.AVAILABLE, false, false, true, 7);

        EvidenceGateResult result = gate.evaluate(packet(duplicate));

        assertThat(result.open()).isFalse();
        assertThat(result.reasons())
                .contains("OBS.SECTOR_REFERENCE:MARKET_SECTOR_NOT_INDEPENDENT");
    }

    private EvidencePacket packet(EvidenceFact... facts) {
        return new EvidencePacket(
                EvidencePacket.SCHEMA_VERSION, "NVDA", "COMMON_STOCK",
                generatedAt, List.of(facts));
    }

    private EvidenceFact fact(
            String id,
            EvidenceQuality quality,
            boolean required,
            boolean pitValid,
            LocalDate asOf,
            OffsetDateTime observedAt,
            int maximumAgeDays
    ) {
        return new EvidenceFact(
                id, DecisionArea.CHART_CROWD, "테스트", "VALUE", asOf, observedAt,
                "TEST_SOURCE", "V1", "COMMON_STOCK", quality, required,
                true, pitValid, maximumAgeDays);
    }
}
