package com.herdsignal.service.decision;

import com.herdsignal.domain.OperatingReviewSnapshot;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;

class OperatingReviewLedgerIntegrityTest {
    private final OperatingReviewLedgerIntegrity integrity = new OperatingReviewLedgerIntegrity();

    @Test
    void verifiesPayloadAndLedgerEnvelopeTogether() {
        OperatingReviewSnapshot unsigned = snapshot("{}", null);
        OperatingReviewSnapshot signed = snapshot(
                "{}", integrity.recordHash(unsigned));

        assertThat(integrity.verify(signed))
                .isEqualTo(OperatingReviewLedgerIntegrity.Status.VERIFIED);
    }

    @Test
    void detectsPayloadOrEnvelopeMutation() {
        OperatingReviewSnapshot unsigned = snapshot("{}", null);
        String recordHash = integrity.recordHash(unsigned);

        assertThat(integrity.verify(snapshot("{\"changed\":true}", recordHash)))
                .isEqualTo(OperatingReviewLedgerIntegrity.Status.MISMATCH);

        OperatingReviewSnapshot changedTicker = OperatingReviewSnapshot.builder()
                .userId(unsigned.getUserId()).ticker("TSLA")
                .reviewedAt(unsigned.getReviewedAt()).observationDate(unsigned.getObservationDate())
                .referencePriceDate(unsigned.getReferencePriceDate())
                .referencePrice(unsigned.getReferencePrice())
                .decisionCode(unsigned.getDecisionCode())
                .actionAuthorized(unsigned.isActionAuthorized())
                .actionRatio(unsigned.getActionRatio())
                .evidenceSchemaVersion(unsigned.getEvidenceSchemaVersion())
                .decisionModelVersion(unsigned.getDecisionModelVersion())
                .payloadJson(unsigned.getPayloadJson()).payloadSha256(unsigned.getPayloadSha256())
                .recordSha256(recordHash).build();
        assertThat(integrity.verify(changedTicker))
                .isEqualTo(OperatingReviewLedgerIntegrity.Status.MISMATCH);
    }

    @Test
    void labelsExistingRowsWithoutEnvelopeHashAsLegacy() {
        assertThat(integrity.verify(snapshot("{}", null)))
                .isEqualTo(OperatingReviewLedgerIntegrity.Status.LEGACY_UNVERIFIED);
    }

    private OperatingReviewSnapshot snapshot(String payload, String recordHash) {
        return OperatingReviewSnapshot.builder()
                .userId("user-1").ticker("NVDA")
                .reviewedAt(LocalDateTime.of(2026, 8, 4, 0, 0))
                .observationDate(LocalDate.of(2026, 8, 1))
                .referencePriceDate(LocalDate.of(2026, 8, 3))
                .referencePrice(new BigDecimal("180.25"))
                .decisionCode("OBSERVE").actionAuthorized(false).actionRatio(BigDecimal.ZERO)
                .evidenceSchemaVersion("LONG_TERM_EVIDENCE_PACKET_V1")
                .decisionModelVersion("LONG_TERM_OPERATING_V1")
                .payloadJson(payload).payloadSha256(integrity.payloadHash("{}"))
                .recordSha256(recordHash).build();
    }
}
