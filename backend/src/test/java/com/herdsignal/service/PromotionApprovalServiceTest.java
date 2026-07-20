package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class PromotionApprovalServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void missingApprovalFileFailsClosed() {
        var service = new PromotionApprovalService(
                new ObjectMapper(), tempDir.resolve("missing.json").toString()
        );

        assertThat(service.isApproved("B9")).isFalse();
    }

    @Test
    void completeFinalAndHumanApprovalAuthorizesExactCandidate() throws Exception {
        Path approval = tempDir.resolve("approval.json");
        Files.writeString(approval, """
                {
                  "policyVersion": "2026.07-v3",
                  "candidateId": "B9",
                  "finalGate": {
                    "status": "PROMOTION_CANDIDATE",
                    "eligibleForHumanReview": true,
                    "automaticProductionPromotion": false
                  },
                  "blindHoldout": {
                    "status": "COMPLETE",
                    "evaluationCount": 1,
                    "passed": true
                  },
                  "humanReview": {
                    "approved": true,
                    "reviewer": "owner",
                    "approvedAt": "2020-01-01T00:00:00Z"
                  }
                }
                """);
        var service = new PromotionApprovalService(
                new ObjectMapper(), approval.toString()
        );

        assertThat(service.isApproved("B9")).isTrue();
        assertThat(service.isApproved("B8")).isFalse();
    }

    @Test
    void holdoutReuseOrMissingHumanApprovalFailsClosed() throws Exception {
        Path approval = tempDir.resolve("invalid.json");
        Files.writeString(approval, """
                {
                  "policyVersion": "2026.07-v3",
                  "candidateId": "B9",
                  "finalGate": {
                    "status": "PROMOTION_CANDIDATE",
                    "eligibleForHumanReview": true,
                    "automaticProductionPromotion": false
                  },
                  "blindHoldout": {
                    "status": "COMPLETE",
                    "evaluationCount": 2,
                    "passed": true
                  },
                  "humanReview": {"approved": false}
                }
                """);
        var service = new PromotionApprovalService(
                new ObjectMapper(), approval.toString()
        );

        assertThat(service.isApproved("B9")).isFalse();
    }
}
