package com.herdsignal.service;

import java.time.Instant;

/** 사람 승인 파일에서 검증을 끝낸 운영 승격 근거. */
public record PromotionEvidence(
        String policyVersion,
        String candidateId,
        String modelVersion,
        String artifactSha256,
        String approvalFileSha256,
        String holdoutId,
        String reviewer,
        Instant approvedAt
) {
}
