package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ExpectationValuationEvidenceAssemblerTest {
    private final ExpectationValuationEvidenceAssembler assembler =
            new ExpectationValuationEvidenceAssembler();
    private final OffsetDateTime generatedAt = OffsetDateTime.parse("2026-08-03T12:00:00Z");

    @Test
    void keepsOnlyTheLatestEligibleAccessionAndLeavesConsensusAndValuationEmpty() {
        ExpectationValuationEvidenceBundle result = assembler.assemble(
                List.of(
                        guidance("old", "0001", "2026-01-15T20:00:00Z"),
                        guidance("new-b", "0002", "2026-07-20T20:00:00Z"),
                        guidance("new-a", "0002", "2026-07-20T20:00:00Z"),
                        guidance("future", "0003", "2026-08-04T20:00:00Z")),
                LocalDate.of(2026, 7, 31),
                generatedAt);

        assertThat(result.assessment().status()).isEqualTo(AssessmentStatus.PARTIAL);
        assertThat(result.assessment().headline()).isEqualTo("경영진 가이던스 원문 2건 확인");
        assertThat(result.facts()).filteredOn(fact -> fact.quality() == EvidenceQuality.AVAILABLE)
                .extracting(EvidenceFact::id)
                .containsExactly(
                        "EXPECTATION.GUIDANCE.new-a",
                        "EXPECTATION.GUIDANCE.new-b");
        assertThat(result.facts()).filteredOn(fact -> fact.quality() == EvidenceQuality.NO_VIEW)
                .extracting(EvidenceFact::id)
                .containsExactly("EXPECTATION.CONSENSUS", "VALUATION.PIT");
        assertThat(result.facts()).allSatisfy(fact -> assertThat(fact.requiredForDecision()).isFalse());
    }

    @Test
    void doesNotUseStaleGuidanceOrCurrentValuationAsAReplacement() {
        ExpectationValuationEvidenceBundle result = assembler.assemble(
                List.of(guidance("stale", "0001", "2024-01-15T20:00:00Z")),
                LocalDate.of(2026, 7, 31),
                generatedAt);

        assertThat(result.assessment().status()).isEqualTo(AssessmentStatus.NO_VIEW);
        assertThat(result.facts()).allSatisfy(fact ->
                assertThat(fact.quality()).isEqualTo(EvidenceQuality.NO_VIEW));
        assertThat(result.facts()).extracting(EvidenceFact::id)
                .containsExactly(
                        "EXPECTATION.CONSENSUS",
                        "VALUATION.PIT",
                        "EXPECTATION.GUIDANCE.PIT");
    }

    private GuidanceEvidenceFactSnapshot guidance(
            String bindingId,
            String accession,
            String acceptedAt
    ) {
        return new GuidanceEvidenceFactSnapshot(
                bindingId, "NVDA", "0001045810", accession,
                OffsetDateTime.parse(acceptedAt), "https://www.sec.gov/example", "abc",
                "HTML_TABLE", "Revenue", "FY2027", "NON_GAAP", "TOTAL", "USD_M",
                new BigDecimal("100"), new BigDecimal("120"), new BigDecimal("110"),
                "HERD_SEC_GUIDANCE_ATOMIC_BINDINGS_V2:test");
    }
}
