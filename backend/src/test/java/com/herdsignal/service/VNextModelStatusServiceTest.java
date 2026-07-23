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
    void rejectedPreHoldoutReportIsExposedWithoutActionAuthority() throws Exception {
        Path report = tempDir.resolve("report.json");
        Files.writeString(report, validRejectedReport());
        VNextModelStatusService service = new VNextModelStatusService(
                objectMapper, report.toString());

        var result = service.getStatus();

        assertThat(result.sourceContractAccepted()).isTrue();
        assertThat(result.validationStatus()).isEqualTo("PATH_MODEL_REJECTED_PREHOLDOUT");
        assertThat(result.decision()).isEqualTo("NO_ADOPTABLE_CANDIDATE");
        assertThat(result.adoptableCandidate()).isFalse();
        assertThat(result.action()).isEqualTo("HOLD");
        assertThat(result.operationalActionRatio()).isZero();
        assertThat(result.userActionSuppressed()).isTrue();
        assertThat(result.blindHoldoutOpened()).isFalse();
        assertThat(result.sourceSha256()).hasSize(64);
        assertThat(result.promotionBlockers()).contains("SURVIVORSHIP_SAFE_FALSE");
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
        Files.writeString(report, validRejectedReport()
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
        Files.writeString(report, validRejectedReport()
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
        Files.writeString(report, validRejectedReport()
                .replace(VNextModelStatusService.EXPECTED_REPORT_VERSION, "UNKNOWN_VERSION"));
        VNextModelStatusService service = new VNextModelStatusService(
                objectMapper, report.toString());

        assertThat(service.getStatus().sourceContractAccepted()).isFalse();
    }

    private String validRejectedReport() {
        return """
                {
                  "report_version": "HERD_VNEXT_PREHOLDOUT_EVALUATION_REPORT_V1",
                  "status": "PATH_MODEL_REJECTED_PREHOLDOUT",
                  "decision": "NO_ADOPTABLE_CANDIDATE",
                  "path_model_passed": false,
                  "protocol": {
                    "protocol_version": "HERD_VNEXT_PREHOLDOUT_EVALUATION_V1",
                    "locked": true,
                    "historical_role": "PRE_HOLDOUT_ONLY",
                    "operational_action_ratio": 0.0
                  },
                  "promotion_blockers": [
                    "PATH_MODEL_PREHOLDOUT_GATE_FAILED",
                    "SURVIVORSHIP_SAFE_FALSE"
                  ],
                  "historical_role": "PRE_HOLDOUT_ONLY",
                  "survivorship_safe": false,
                  "prospective_shadow_status": "BLOCKED_PATH_MODEL_FAILED",
                  "operational_action_ratio": 0.0,
                  "blind_holdout_access": false
                }
                """;
    }
}
