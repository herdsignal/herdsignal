package com.herdsignal.service;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class ShadowModelStatusServiceTest {

    @Test
    void failedResearchGateKeepsShadowDisabled() {
        ShadowModelStatusService service = new ShadowModelStatusService(
                false, "", gateWithoutEvidence(false)
        );

        var result = service.getStatus();

        assertThat(result.shadowStatus()).isEqualTo("DISABLED_RESEARCH_GATE_FAILED");
        assertThat(result.productionModel()).isEqualTo("HERD_STATE_S1_ACTION_CANDIDATE");
        assertThat(result.productionOutputUnaffected()).isTrue();
        assertThat(result.userActionSuppressed()).isTrue();
    }

    @Test
    void enabledFlagCannotBypassMissingCandidate() {
        ShadowModelStatusService service = new ShadowModelStatusService(
                true, "", gateWithEvidence("B3")
        );

        assertThat(service.getStatus().shadowStatus()).isEqualTo("BLOCKED_INVALID_CONFIGURATION");
    }

    @Test
    void booleanApprovalCannotReplaceAuditableEvidence() {
        ShadowModelStatusService service = new ShadowModelStatusService(
                true, "B3", gateWithoutEvidence(true)
        );

        assertThat(service.getStatus().shadowStatus())
                .isEqualTo("BLOCKED_INVALID_CONFIGURATION");
    }

    @Test
    void candidateWithAuditableEvidenceCanOnlyEnterShadowMode() {
        ShadowModelStatusService service = new ShadowModelStatusService(
                true, "B5", gateWithEvidence("B5")
        );

        var result = service.getStatus();

        assertThat(result.shadowStatus()).isEqualTo("SHADOW_ACTIVE");
        assertThat(result.candidateId()).isEqualTo("B5");
        assertThat(result.productionOutputUnaffected()).isTrue();
        assertThat(result.userActionSuppressed()).isTrue();
    }

    private static OperationalPromotionGate gateWithoutEvidence(boolean approved) {
        return ignored -> approved;
    }

    private static OperationalPromotionGate gateWithEvidence(String approvedCandidateId) {
        return new OperationalPromotionGate() {
            @Override
            public boolean isApproved(String candidateId) {
                return approvedCandidateId.equals(candidateId);
            }

            @Override
            public Optional<PromotionEvidence> approvalEvidence(String candidateId) {
                if (!approvedCandidateId.equals(candidateId)) {
                    return Optional.empty();
                }
                return Optional.of(new PromotionEvidence(
                        "2026.07-v3",
                        candidateId,
                        "HERD_STATE_S1_ACTION_CANDIDATE",
                        "a".repeat(64),
                        "b".repeat(64),
                        "blind-holdout-1",
                        "reviewer",
                        Instant.parse("2026-07-28T00:00:00Z")
                ));
            }
        };
    }
}
