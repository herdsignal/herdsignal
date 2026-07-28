package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.VNextModelStatusResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

/**
 * 최신 개인 MVP 승격 판정을 운영 응답과 격리된 읽기 전용 상태로 변환한다.
 *
 * <p>이 서비스는 후보를 승격하지 않는다. 입력이 없거나 예상 계약에서
 * 벗어나면 항상 행동 권한을 차단하는 fail-closed 응답을 반환한다.</p>
 */
@Service
public class VNextModelStatusService {

    static final String EXPECTED_REPORT_VERSION =
            "HERD_PERSONAL_ACTION_REVIEW_GATE_V2";
    private static final String MODEL_FAMILY = "HERD_STATE_S1";
    private static final String LIFECYCLE = "PERSONAL_RESEARCH_MVP";
    private static final String NO_CANDIDATE = "NO_ADOPTABLE_ACTION_CANDIDATE";
    private static final String HOLD = "HOLD";
    private static final String HERD_STATE_ROLE = "HERD_STATE_S1_OBSERVATION";

    private final ObjectMapper objectMapper;
    private final Path reportPath;

    public VNextModelStatusService(
            ObjectMapper objectMapper,
            @Value("${herdsignal.vnext.promotion-report-path:"
                    + "../data/reports/personal_action_review_gate_v2.json}")
            String reportPath
    ) {
        this.objectMapper = objectMapper;
        this.reportPath = Path.of(reportPath).toAbsolutePath().normalize();
    }

    public VNextModelStatusResponse getStatus() {
        try {
            if (!Files.isRegularFile(reportPath)) {
                return failClosed(
                        "REPORT_UNAVAILABLE",
                        "PERSONAL_MVP_PROMOTION_REPORT_UNAVAILABLE"
                );
            }
            byte[] source = Files.readAllBytes(reportPath);
            JsonNode root = objectMapper.readTree(source);
            if (root == null || !root.isObject()) {
                throw new IllegalArgumentException("vNext 판정 파일은 JSON 객체여야 합니다.");
            }
            validatePersonalMvpContract(root);
            return accepted(root, sha256(source));
        } catch (IOException | IllegalArgumentException | NoSuchAlgorithmException exception) {
            return failClosed(
                    "REPORT_INVALID",
                    "PERSONAL_MVP_PROMOTION_REPORT_INVALID"
            );
        }
    }

    private void validatePersonalMvpContract(JsonNode root) {
        requireText(root, "report_version", EXPECTED_REPORT_VERSION);
        requireText(root, "status", "STATE_OBSERVATION_MVP_READY");
        requireText(root, "decision", NO_CANDIDATE);
        requireText(root, "model_family", MODEL_FAMILY);
        requireText(root, "lifecycle", LIFECYCLE);
        requireText(root, "herd_state_role", HERD_STATE_ROLE);
        requireText(
                root,
                "historical_role",
                "CURRENT_CONSTITUENTS_DESCRIPTIVE_ONLY"
        );
        requireText(
                root,
                "prospective_shadow_status",
                "STATE_ONLY_ACTION_SHADOW_BLOCKED"
        );
        requireText(root, "default_action", HOLD);
        requireBoolean(root, "state_observation_ready", true);
        requireBoolean(root, "transition_observation_ready", true);
        requireBoolean(root, "action_candidate_ready", false);
        requireBoolean(root, "user_action_suppressed", true);
        requireText(
                root,
                "action_model_status",
                "INDEPENDENT_DIRECTION_EVIDENCE_REJECTED"
        );
        requireBoolean(root, "survivorship_safe", false);
        requireBoolean(root, "blind_holdout_access", false);
        requireZeroRatio(root, "operational_action_ratio");

        JsonNode blockers = root.path("promotion_blockers");
        requireStringArrayContains(
                blockers,
                "승격 차단 사유",
                "PROFIT_TAKE_DIRECTION_NOT_PASSED",
                "CONDITIONAL_REENTRY_NOT_PASSED",
                "COMPLETED_CYCLE_NOT_PASSED",
                "PROSPECTIVE_SHADOW_NOT_PASSED",
                "SURVIVORSHIP_SAFE_NOT_PASSED"
        );
        JsonNode allowedScope = root.path("allowed_scope");
        JsonNode blockedScope = root.path("blocked_scope");
        requireStringArrayContains(
                allowedScope,
                "허용 기능",
                "HERD_STATE_S1",
                "HERD_TRANSITION_S1"
        );
        requireStringArrayContains(
                blockedScope,
                "차단 기능",
                "BUY_RATIO",
                "PROFIT_TAKE_RATIO",
                "REENTRY_RATIO"
        );
    }

    private VNextModelStatusResponse accepted(JsonNode root, String sourceSha256) {
        return new VNextModelStatusResponse(
                MODEL_FAMILY,
                LIFECYCLE,
                root.path("status").asText(),
                NO_CANDIDATE,
                true,
                false,
                HOLD,
                BigDecimal.ZERO,
                true,
                HERD_STATE_ROLE,
                root.path("historical_role").asText(),
                false,
                false,
                root.path("prospective_shadow_status").asText(),
                EXPECTED_REPORT_VERSION,
                sourceSha256,
                strings(root.path("promotion_blockers"))
        );
    }

    private VNextModelStatusResponse failClosed(String validationStatus, String blocker) {
        return new VNextModelStatusResponse(
                MODEL_FAMILY,
                LIFECYCLE,
                validationStatus,
                NO_CANDIDATE,
                false,
                false,
                HOLD,
                BigDecimal.ZERO,
                true,
                HERD_STATE_ROLE,
                "CURRENT_CONSTITUENTS_DESCRIPTIVE_ONLY",
                false,
                false,
                "BLOCKED_SOURCE_CONTRACT",
                null,
                null,
                List.of(blocker)
        );
    }

    private static void requireText(JsonNode root, String field, String expected) {
        if (!expected.equals(root.path(field).asText(null))) {
            throw new IllegalArgumentException("예상하지 않은 필드: " + field);
        }
    }

    private static void requireBoolean(JsonNode root, String field, boolean expected) {
        JsonNode value = root.path(field);
        if (!value.isBoolean() || value.asBoolean() != expected) {
            throw new IllegalArgumentException("예상하지 않은 필드: " + field);
        }
    }

    private static void requireZeroRatio(JsonNode root, String field) {
        JsonNode value = root.path(field);
        if (!value.isNumber()
                || value.decimalValue().compareTo(BigDecimal.ZERO) != 0) {
            throw new IllegalArgumentException("운영 행동 비율은 0이어야 합니다.");
        }
    }

    private static void requireStringArrayContains(
            JsonNode node,
            String label,
            String... required
    ) {
        if (!node.isArray() || node.isEmpty()) {
            throw new IllegalArgumentException(label + " 목록이 필요합니다.");
        }
        List<String> values = strings(node);
        for (String value : required) {
            if (!values.contains(value)) {
                throw new IllegalArgumentException(label + " 누락: " + value);
            }
        }
    }

    private static List<String> strings(JsonNode node) {
        List<String> values = new ArrayList<>();
        node.forEach(value -> values.add(value.asText()));
        return List.copyOf(values);
    }

    private static String sha256(byte[] source) throws NoSuchAlgorithmException {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(source));
    }
}
