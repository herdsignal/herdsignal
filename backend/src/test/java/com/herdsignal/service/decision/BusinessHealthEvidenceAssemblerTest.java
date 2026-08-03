package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class BusinessHealthEvidenceAssemblerTest {
    private final BusinessHealthEvidenceAssembler assembler = new BusinessHealthEvidenceAssembler();
    private final OffsetDateTime generatedAt = OffsetDateTime.parse("2026-08-03T12:00:00Z");

    @Test
    void groupsAvailablePitFactsWithoutCreatingDirectionOrActionAuthority() {
        BusinessHealthEvidenceBundle result = assembler.assemble(
                Optional.of(snapshot("PIT_FACTS_READY", "GENERAL")),
                LocalDate.of(2026, 7, 31),
                generatedAt);

        assertThat(result.assessment().status()).isEqualTo(AssessmentStatus.PARTIAL);
        assertThat(result.assessment().headline()).isEqualTo("SEC PIT 기업 사실 6/6 확인");
        assertThat(result.facts()).hasSize(8);
        assertThat(result.facts()).allSatisfy(fact -> {
            assertThat(fact.area()).isEqualTo(DecisionArea.BUSINESS_HEALTH);
            assertThat(fact.requiredForDecision()).isFalse();
            assertThat(fact.pointInTimeRequired()).isTrue();
            assertThat(fact.source()).isEqualTo("SEC_COMPANY_FACTS");
        });
    }

    @Test
    void reportsPartialMetricCoverageWithoutFillingMissingFacts() {
        BusinessEvidenceSnapshot row = snapshot("PIT_FACTS_READY", "GENERAL");
        row = new BusinessEvidenceSnapshot(
                row.ticker(), row.cik(), row.featureMonthEnd(), row.corpusStatus(),
                row.latestFactAcceptedAt(), row.entityType(), row.sourceVersion(),
                row.revenueYoy(), null, null, row.operatingCashFlowYoy(),
                row.operatingCashFlowValue(), row.liabilitiesToAssets(),
                row.liabilitiesToAssetsYoyChange());

        BusinessHealthEvidenceBundle result = assembler.assemble(
                Optional.of(row), LocalDate.of(2026, 7, 31), generatedAt);

        assertThat(result.assessment().headline()).isEqualTo("SEC PIT 기업 사실 4/6 확인");
        assertThat(result.facts()).filteredOn(fact -> fact.quality() == EvidenceQuality.NO_VIEW)
                .extracting(EvidenceFact::id)
                .containsExactlyInAnyOrder(
                        "BUSINESS.PIT.NET_MARGIN",
                        "BUSINESS.PIT.NET_MARGIN_YOY_CHANGE");
    }

    @Test
    void failsClosedForUnsupportedEntityTypes() {
        BusinessHealthEvidenceBundle result = assembler.assemble(
                Optional.of(snapshot("PIT_FACTS_READY", "BANK")),
                LocalDate.of(2026, 7, 31),
                generatedAt);

        assertThat(result.assessment().status()).isEqualTo(AssessmentStatus.NO_VIEW);
        assertThat(result.assessment().headline()).isEqualTo("BANK 측정법 미지원");
        assertThat(result.facts()).singleElement().satisfies(fact -> {
            assertThat(fact.quality()).isEqualTo(EvidenceQuality.NO_VIEW);
            assertThat(fact.value()).contains("전용 측정법");
        });
    }

    private BusinessEvidenceSnapshot snapshot(String corpusStatus, String entityType) {
        return new BusinessEvidenceSnapshot(
                "NVDA", "0001045810", LocalDate.of(2026, 6, 30), corpusStatus,
                OffsetDateTime.parse("2026-05-20T20:00:00Z"), entityType,
                "HERD_SEC_PIT_BUSINESS_FACTS_V1:test",
                decimal("0.20"), decimal("0.30"), decimal("0.01"),
                decimal("0.40"), decimal("100"), decimal("0.25"), decimal("-0.02"));
    }

    private BigDecimal decimal(String value) {
        return new BigDecimal(value);
    }
}
