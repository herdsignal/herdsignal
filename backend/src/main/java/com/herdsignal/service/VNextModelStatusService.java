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
 * vNext pre-holdout 판정을 운영 응답과 격리된 읽기 전용 상태로 변환한다.
 *
 * <p>이 서비스는 후보를 승격하지 않는다. 입력이 없거나 예상 계약에서
 * 벗어나면 항상 행동 권한을 차단하는 fail-closed 응답을 반환한다.</p>
 */
@Service
public class VNextModelStatusService {

    static final String EXPECTED_REPORT_VERSION = "HERD_VNEXT_PREHOLDOUT_EVALUATION_REPORT_V1";
    private static final String MODEL_FAMILY = "HERD_VNEXT_RESEARCH";
    private static final String LIFECYCLE = "RESEARCH_VALIDATION";
    private static final String NO_CANDIDATE = "NO_ADOPTABLE_CANDIDATE";
    private static final String HOLD = "HOLD";
    private static final String HERD_STATE_ROLE = "HERD_v4_LEGACY_STATE_BASELINE";

    private final ObjectMapper objectMapper;
    private final Path reportPath;

    public VNextModelStatusService(
            ObjectMapper objectMapper,
            @Value("${herdsignal.vnext.preholdout-report-path:"
                    + "../data/reports/vnext_preholdout_evaluation_v1.json}")
            String reportPath
    ) {
        this.objectMapper = objectMapper;
        this.reportPath = Path.of(reportPath).toAbsolutePath().normalize();
    }

    public VNextModelStatusResponse getStatus() {
        try {
            if (!Files.isRegularFile(reportPath)) {
                return failClosed("REPORT_UNAVAILABLE", "VNEXT_PREHOLDOUT_REPORT_UNAVAILABLE");
            }
            byte[] source = Files.readAllBytes(reportPath);
            JsonNode root = objectMapper.readTree(source);
            if (root == null || !root.isObject()) {
                throw new IllegalArgumentException("vNext 판정 파일은 JSON 객체여야 합니다.");
            }
            validateRejectedPreHoldoutContract(root);
            return accepted(root, sha256(source));
        } catch (IOException | IllegalArgumentException | NoSuchAlgorithmException exception) {
            return failClosed("REPORT_INVALID", "VNEXT_PREHOLDOUT_REPORT_INVALID");
        }
    }

    private void validateRejectedPreHoldoutContract(JsonNode root) {
        requireText(root, "report_version", EXPECTED_REPORT_VERSION);
        requireText(root, "status", "PATH_MODEL_REJECTED_PREHOLDOUT");
        requireText(root, "decision", NO_CANDIDATE);
        requireText(root, "historical_role", "PRE_HOLDOUT_ONLY");
        requireText(root, "prospective_shadow_status", "BLOCKED_PATH_MODEL_FAILED");
        requireBoolean(root, "path_model_passed", false);
        requireBoolean(root, "survivorship_safe", false);
        requireBoolean(root, "blind_holdout_access", false);

        JsonNode ratio = root.path("operational_action_ratio");
        if (!ratio.isNumber() || ratio.decimalValue().compareTo(BigDecimal.ZERO) != 0) {
            throw new IllegalArgumentException("운영 행동 비율은 0이어야 합니다.");
        }

        JsonNode blockers = root.path("promotion_blockers");
        if (!blockers.isArray() || blockers.isEmpty()) {
            throw new IllegalArgumentException("승격 차단 사유가 필요합니다.");
        }
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
                "PRE_HOLDOUT_ONLY",
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

    private static List<String> strings(JsonNode node) {
        List<String> values = new ArrayList<>();
        node.forEach(value -> values.add(value.asText()));
        return List.copyOf(values);
    }

    private static String sha256(byte[] source) throws NoSuchAlgorithmException {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(source));
    }
}
