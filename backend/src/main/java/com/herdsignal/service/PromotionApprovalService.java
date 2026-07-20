package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;

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
        if (!StringUtils.hasText(candidateId) || approvalPath == null
                || !Files.isRegularFile(approvalPath)) {
            return false;
        }
        try {
            JsonNode root = objectMapper.readTree(approvalPath.toFile());
            JsonNode finalGate = root.path("finalGate");
            JsonNode holdout = root.path("blindHoldout");
            JsonNode humanReview = root.path("humanReview");
            return POLICY_VERSION.equals(root.path("policyVersion").asText())
                    && candidateId.trim().equals(root.path("candidateId").asText())
                    && "PROMOTION_CANDIDATE".equals(finalGate.path("status").asText())
                    && finalGate.path("eligibleForHumanReview").asBoolean(false)
                    && !finalGate.path("automaticProductionPromotion").asBoolean(true)
                    && "COMPLETE".equals(holdout.path("status").asText())
                    && holdout.path("evaluationCount").asInt(0) == 1
                    && holdout.path("passed").asBoolean(false)
                    && humanReview.path("approved").asBoolean(false)
                    && StringUtils.hasText(humanReview.path("reviewer").asText())
                    && validApprovalTime(humanReview.path("approvedAt").asText());
        } catch (IOException | RuntimeException ignored) {
            return false;
        }
    }

    private boolean validApprovalTime(String value) {
        if (!StringUtils.hasText(value)) {
            return false;
        }
        Instant approvedAt = Instant.parse(value);
        return !approvedAt.isAfter(Instant.now());
    }
}
