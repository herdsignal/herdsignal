package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class VNextModelStatusServiceTest {

    @TempDir
    Path tempDir;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void stateObservationMvpIsExposedWithoutActionAuthority() throws Exception {
        Path report = tempDir.resolve("report.json");
        Files.writeString(report, validPromotionReport());
        VNextModelStatusService service = new VNextModelStatusService(
                objectMapper, report.toString());

        var result = service.getStatus();

        assertThat(result.sourceContractAccepted()).isTrue();
        assertThat(result.validationStatus()).isEqualTo("STATE_OBSERVATION_MVP_READY");
        assertThat(result.decision()).isEqualTo("NO_ADOPTABLE_ACTION_CANDIDATE");
        assertThat(result.adoptableCandidate()).isFalse();
        assertThat(result.action()).isEqualTo("HOLD");
        assertThat(result.operationalActionRatio()).isZero();
        assertThat(result.userActionSuppressed()).isTrue();
        assertThat(result.blindHoldoutOpened()).isFalse();
        assertThat(result.sourceSha256()).hasSize(64);
        assertThat(result.herdStateRole()).isEqualTo("HERD_STATE_S1_OBSERVATION");
        assertThat(result.promotionBlockers())
                .contains("SURVIVORSHIP_SAFE_NOT_PASSED");
    }

    @Test
    void missingReportFailsClosed() {
        VNextModelStatusService service = new VNextModelStatusService(
                objectMapper, tempDir.resolve("missing.json").toString());

        var result = service.getStatus();

        assertThat(result.sourceContractAccepted()).isFalse();
        assertThat(result.validationStatus()).isEqualTo("REPORT_UNAVAILABLE");
        assertThat(result.action()).isEqualTo("HOLD");
        assertThat(result.operationalActionRatio()).isZero();
        assertThat(result.userActionSuppressed()).isTrue();
    }

    @Test
    void nonZeroActionRatioCannotBypassResearchGate() throws Exception {
        Path report = tempDir.resolve("unsafe.json");
        Files.writeString(report, validPromotionReport()
                .replace("\"operational_action_ratio\": 0.0",
                        "\"operational_action_ratio\": 0.05"));
        VNextModelStatusService service = new VNextModelStatusService(
                objectMapper, report.toString());

        var result = service.getStatus();

        assertThat(result.sourceContractAccepted()).isFalse();
        assertThat(result.validationStatus()).isEqualTo("REPORT_INVALID");
        assertThat(result.action()).isEqualTo("HOLD");
        assertThat(result.operationalActionRatio()).isZero();
    }

    @Test
    void openedBlindHoldoutCannotBeSilentlyAccepted() throws Exception {
        Path report = tempDir.resolve("opened.json");
        Files.writeString(report, validPromotionReport()
                .replace("\"blind_holdout_access\": false",
                        "\"blind_holdout_access\": true"));
        VNextModelStatusService service = new VNextModelStatusService(
                objectMapper, report.toString());

        var result = service.getStatus();

        assertThat(result.sourceContractAccepted()).isFalse();
        assertThat(result.validationStatus()).isEqualTo("REPORT_INVALID");
        assertThat(result.blindHoldoutOpened()).isFalse();
        assertThat(result.userActionSuppressed()).isTrue();
    }

    @Test
    void unknownReportVersionCannotBeAccepted() throws Exception {
        Path report = tempDir.resolve("unknown.json");
        Files.writeString(report, validPromotionReport()
                .replace(VNextModelStatusService.EXPECTED_REPORT_VERSION, "UNKNOWN_VERSION"));
        VNextModelStatusService service = new VNextModelStatusService(
                objectMapper, report.toString());

        assertThat(service.getStatus().sourceContractAccepted()).isFalse();
    }

    @Test
    void missingActionBlockerCannotBeAccepted() throws Exception {
        Path report = tempDir.resolve("missing-blocker.json");
        Files.writeString(report, validPromotionReport()
                .replace(", \"REENTRY_RATIO\"", ""));
        VNextModelStatusService service = new VNextModelStatusService(
                objectMapper, report.toString());

        assertThat(service.getStatus().sourceContractAccepted()).isFalse();
        assertThat(service.getStatus().operationalActionRatio()).isZero();
    }

    private String validPromotionReport() {
        return """
                {
                  "report_version": "HERD_PERSONAL_ACTION_REVIEW_GATE_V2",
                  "status": "STATE_OBSERVATION_MVP_READY",
                  "decision": "NO_ADOPTABLE_ACTION_CANDIDATE",
                  "model_family": "HERD_STATE_S1",
                  "lifecycle": "PERSONAL_RESEARCH_MVP",
                  "state_observation_ready": true,
                  "transition_observation_ready": true,
                  "action_candidate_ready": false,
                  "action_model_status": "INDEPENDENT_DIRECTION_EVIDENCE_REJECTED",
                  "allowed_scope": ["HERD_STATE_S1", "HERD_TRANSITION_S1"],
                  "blocked_scope": ["BUY_RATIO", "PROFIT_TAKE_RATIO", "REENTRY_RATIO"],
                  "default_action": "HOLD",
                  "user_action_suppressed": true,
                  "herd_state_role": "HERD_STATE_S1_OBSERVATION",
                  "promotion_blockers": [
                    "PROFIT_TAKE_DIRECTION_NOT_PASSED",
                    "CONDITIONAL_REENTRY_NOT_PASSED",
                    "COMPLETED_CYCLE_NOT_PASSED",
                    "PROSPECTIVE_SHADOW_NOT_PASSED",
                    "SURVIVORSHIP_SAFE_NOT_PASSED"
                  ],
                  "historical_role": "CURRENT_CONSTITUENTS_DESCRIPTIVE_ONLY",
                  "survivorship_safe": false,
                  "prospective_shadow_status": "STATE_ONLY_ACTION_SHADOW_BLOCKED",
                  "operational_action_ratio": 0.0,
                  "blind_holdout_access": false
                }
                """;
    }
}
