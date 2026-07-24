package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Optional;

/** 최종 게이트·단일 holdout·사람 승인이 기록된 파일만 운영 승격 근거로 인정한다. */
@Service
public class PromotionApprovalService implements OperationalPromotionGate {

    private static final String POLICY_VERSION = "2026.07-v3";
    private final ObjectMapper objectMapper;
    private final Path approvalPath;

    public PromotionApprovalService(
            ObjectMapper objectMapper,
            @Value("${herdsignal.promotion.approval-path:}") String approvalPath
    ) {
        this.objectMapper = objectMapper;
        this.approvalPath = StringUtils.hasText(approvalPath)
                ? Path.of(approvalPath).toAbsolutePath().normalize()
                : null;
    }

    @Override
    public boolean isApproved(String candidateId) {
        return approvalEvidence(candidateId).isPresent();
    }

    @Override
    public Optional<PromotionEvidence> approvalEvidence(String candidateId) {
        if (!StringUtils.hasText(candidateId) || approvalPath == null
                || !Files.isRegularFile(approvalPath)) {
            return Optional.empty();
        }
        try {
            byte[] approvalBytes = Files.readAllBytes(approvalPath);
            JsonNode root = objectMapper.readTree(approvalBytes);
            JsonNode finalGate = root.path("finalGate");
            JsonNode holdout = root.path("blindHoldout");
            JsonNode humanReview = root.path("humanReview");
            String modelVersion = root.path("modelVersion").asText();
            String artifactSha256 = root.path("artifactSha256").asText();
            String holdoutId = holdout.path("id").asText();
            String reviewer = humanReview.path("reviewer").asText();
            Instant approvedAt = approvalTime(humanReview.path("approvedAt").asText());
            boolean approved = POLICY_VERSION.equals(root.path("policyVersion").asText())
                    && candidateId.trim().equals(root.path("candidateId").asText())
                    && StringUtils.hasText(modelVersion)
                    && validSha256(artifactSha256)
                    && "PROMOTION_CANDIDATE".equals(finalGate.path("status").asText())
                    && finalGate.path("eligibleForHumanReview").asBoolean(false)
                    && !finalGate.path("automaticProductionPromotion").asBoolean(true)
                    && finalGate.path("directionEvidencePassed").asBoolean(false)
                    && finalGate.path("completedCyclePassed").asBoolean(false)
                    && finalGate.path("survivorshipSafe").asBoolean(false)
                    && StringUtils.hasText(holdoutId)
                    && "COMPLETE".equals(holdout.path("status").asText())
                    && holdout.path("evaluationCount").asInt(0) == 1
                    && holdout.path("passed").asBoolean(false)
                    && humanReview.path("approved").asBoolean(false)
                    && StringUtils.hasText(reviewer)
                    && approvedAt != null;
            if (!approved) {
                return Optional.empty();
            }
            return Optional.of(new PromotionEvidence(
                    POLICY_VERSION,
                    candidateId.trim(),
                    modelVersion,
                    artifactSha256.toLowerCase(),
                    sha256(approvalBytes),
                    holdoutId,
                    reviewer,
                    approvedAt
            ));
        } catch (IOException | NoSuchAlgorithmException | RuntimeException ignored) {
            return Optional.empty();
        }
    }

    private Instant approvalTime(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        Instant approvedAt = Instant.parse(value);
        return approvedAt.isAfter(Instant.now()) ? null : approvedAt;
    }

    private boolean validSha256(String value) {
        return value != null && value.matches("(?i)^[0-9a-f]{64}$");
    }

    private String sha256(byte[] content) throws NoSuchAlgorithmException {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        return HexFormat.of().formatHex(digest.digest(content));
    }
}
