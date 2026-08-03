package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.OffsetDateTime;

import static org.assertj.core.api.Assertions.assertThat;

class InformationChangeEvidenceAssemblerTest {
    private final InformationChangeEvidenceAssembler assembler =
            new InformationChangeEvidenceAssembler();

    @Test
    void exposesSourceSpecificNoViewReasonsWithoutCreatingDirection() {
        InformationChangeEvidenceBundle result = assembler.assemble(
                LocalDate.of(2026, 8, 1),
                OffsetDateTime.parse("2026-08-03T12:00:00Z"));

        assertThat(result.assessment().status()).isEqualTo(AssessmentStatus.NO_VIEW);
        assertThat(result.assessment().evidenceIds()).isEmpty();
        assertThat(result.facts()).extracting(EvidenceFact::id)
                .containsExactly(
                        "INFO.SEC.MATERIAL_EVENT",
                        "INFO.SEC.FORM4",
                        "INFO.POSITIONING",
                        "INFO.NEWS.PIT");
        assertThat(result.facts()).allSatisfy(fact -> {
            assertThat(fact.quality()).isEqualTo(EvidenceQuality.NO_VIEW);
            assertThat(fact.requiredForDecision()).isFalse();
            assertThat(fact.value()).isNotBlank();
        });
    }
}
