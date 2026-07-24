package com.herdsignal.service;

import com.herdsignal.domain.ModelPromotionAudit;
import com.herdsignal.repository.ModelPromotionAuditRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AuditedOperationalActionPromotionPortTest {

    private static final String ARTIFACT_HASH = "a".repeat(64);
    private OperationalPromotionGate gate;
    private ModelPromotionAuditRepository repository;
    private AuditedOperationalActionPromotionPort port;

    @BeforeEach
    void setUp() {
        gate = mock(OperationalPromotionGate.class);
        repository = mock(ModelPromotionAuditRepository.class);
        when(repository.saveAndFlush(any(ModelPromotionAudit.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        port = new AuditedOperationalActionPromotionPort(
                gate,
                repository,
                Clock.fixed(
                        Instant.parse("2026-07-25T00:00:00Z"),
                        ZoneOffset.UTC
                )
        );
    }

    @Test
    void grantsOnlyAHashMatchedFivePercentPartialActionAndAuditsIt() {
        when(gate.approvalEvidence("CANDIDATE_S2"))
                .thenReturn(Optional.of(evidence()));

        Optional<GrantedOperationalAction> result = port.request(request(
                "HERD_ACTION_S2", ARTIFACT_HASH, "REDUCE", "0.0500"
        ));

        assertThat(result).isPresent();
        UserActionBoundary.Output output = new UserActionBoundary()
                .fromApproved(result.orElseThrow());
        assertThat(output.action()).isEqualTo("REDUCE");
        assertThat(output.ratio()).isEqualByComparingTo("0.05");
        assertThat(output.authorized()).isTrue();
        assertThat(output.directionPrediction()).isTrue();

        ArgumentCaptor<ModelPromotionAudit> audit =
                ArgumentCaptor.forClass(ModelPromotionAudit.class);
        verify(repository).saveAndFlush(audit.capture());
        assertThat(audit.getValue().getDecision()).isEqualTo("GRANTED");
        assertThat(audit.getValue().getReasonCode())
                .isEqualTo("ALL_GATES_PASSED");
        assertThat(audit.getValue().getApprovalFileSha256()).hasSize(64);
    }

    @Test
    void rejectsMissingEvidenceAndHashMismatch() {
        port.request(request(
                "HERD_ACTION_S2", ARTIFACT_HASH, "ADD", "0.0500"
        ));
        when(gate.approvalEvidence("CANDIDATE_S2"))
                .thenReturn(Optional.of(evidence()));
        Optional<GrantedOperationalAction> mismatch = port.request(request(
                "HERD_ACTION_S2", "b".repeat(64), "ADD", "0.0500"
        ));

        assertThat(mismatch).isEmpty();
        ArgumentCaptor<ModelPromotionAudit> audits =
                ArgumentCaptor.forClass(ModelPromotionAudit.class);
        verify(repository, org.mockito.Mockito.times(2))
                .saveAndFlush(audits.capture());
        assertThat(audits.getAllValues())
                .extracting(ModelPromotionAudit::getReasonCode)
                .containsExactly(
                        "APPROVAL_EVIDENCE_MISSING",
                        "ARTIFACT_HASH_MISMATCH"
                );
    }

    @Test
    void rejectsFullTradeCodesAndRatiosAboveFivePercent() {
        when(gate.approvalEvidence("CANDIDATE_S2"))
                .thenReturn(Optional.of(evidence()));

        assertThat(port.request(request(
                "HERD_ACTION_S2", ARTIFACT_HASH, "SELL", "0.0500"
        ))).isEmpty();
        assertThat(port.request(request(
                "HERD_ACTION_S2", ARTIFACT_HASH, "REDUCE", "0.0501"
        ))).isEmpty();
    }

    @Test
    void failsClosedWhenTheAuditCannotBePersisted() {
        when(gate.approvalEvidence("CANDIDATE_S2"))
                .thenReturn(Optional.of(evidence()));
        when(repository.saveAndFlush(any(ModelPromotionAudit.class)))
                .thenThrow(new IllegalStateException("db unavailable"));

        assertThat(port.request(request(
                "HERD_ACTION_S2", ARTIFACT_HASH, "ADD", "0.0500"
        ))).isEmpty();
    }

    private OperationalActionPromotionRequest request(
            String modelVersion,
            String hash,
            String action,
            String ratio
    ) {
        return new OperationalActionPromotionRequest(
                "CANDIDATE_S2",
                modelVersion,
                hash,
                "NVDA",
                action,
                new BigDecimal(ratio),
                LocalDate.of(2026, 7, 24)
        );
    }

    private PromotionEvidence evidence() {
        return new PromotionEvidence(
                "2026.07-v3",
                "CANDIDATE_S2",
                "HERD_ACTION_S2",
                ARTIFACT_HASH,
                "c".repeat(64),
                "BLIND_2027_H1",
                "owner",
                Instant.parse("2026-07-20T00:00:00Z")
        );
    }
}
