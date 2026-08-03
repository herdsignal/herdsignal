package com.herdsignal.service.decision;

import com.herdsignal.service.EvidenceAdmissionAuthority;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class OperatingActionAuthorizationGateTest {

    @Test
    void blocksRequestedActionsWhenCurrentEvidenceHasNoAuthority() {
        OperatingActionAuthorizationGate gate = new OperatingActionAuthorizationGate(
                authority(false, 0, 0, 0, "0.0"));

        DecisionSynthesis result = gate.enforce(request(
                OperatingDecisionCode.REVIEW_TRIM, 0.05));

        assertThat(result.decision()).isEqualTo(OperatingDecisionCode.OBSERVE);
        assertThat(result.actionAuthorized()).isFalse();
        assertThat(result.operationalActionRatio()).isZero();
        assertThat(result.limitations()).contains("OPERATIONAL_ACTION_NOT_PROMOTED");
    }

    @Test
    void requiresBusinessVetoTogetherWithAddDirection() {
        OperatingActionAuthorizationGate gate = new OperatingActionAuthorizationGate(
                authority(true, 0, 1, 0, "0.05"));

        DecisionSynthesis result = gate.enforce(request(
                OperatingDecisionCode.REVIEW_ADD, 0.05));

        assertThat(result.decision()).isEqualTo(OperatingDecisionCode.OBSERVE);
        assertThat(result.limitations()).contains("BUSINESS_VETO_EVIDENCE_NOT_ADMITTED");
    }

    @Test
    void allowsOnlyAWithinCapRequestWithMatchingAdmittedEvidence() {
        OperatingActionAuthorizationGate gate = new OperatingActionAuthorizationGate(
                authority(true, 1, 1, 1, "0.05"));

        DecisionSynthesis trim = gate.enforce(request(
                OperatingDecisionCode.REVIEW_TRIM, 0.05));
        DecisionSynthesis excessiveAdd = gate.enforce(request(
                OperatingDecisionCode.REVIEW_ADD, 0.10));

        assertThat(trim.decision()).isEqualTo(OperatingDecisionCode.REVIEW_TRIM);
        assertThat(trim.actionAuthorized()).isTrue();
        assertThat(excessiveAdd.decision()).isEqualTo(OperatingDecisionCode.OBSERVE);
        assertThat(excessiveAdd.limitations()).contains("ACTION_RATIO_EXCEEDS_AUTHORITY");
    }

    private EvidenceAdmissionAuthority authority(
            boolean operational,
            int trim,
            int add,
            int veto,
            String ratio
    ) {
        return new EvidenceAdmissionAuthority(
                true, trim, add, veto, false, operational,
                new BigDecimal(ratio), List.of());
    }

    private DecisionSynthesis request(OperatingDecisionCode code, double ratio) {
        return new DecisionSynthesis(
                code, "후보", List.of("EVIDENCE.X"), List.of(),
                true, code == OperatingDecisionCode.REVIEW_ADD ? "ADD" : "TRIM", ratio);
    }
}
