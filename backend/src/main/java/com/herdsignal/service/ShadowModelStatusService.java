package com.herdsignal.service;

import com.herdsignal.dto.ShadowModelStatusResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/** 검증을 통과하지 않은 모델이 운영 응답에 섞이지 않도록 shadow 상태를 판정한다. */
@Service
public class ShadowModelStatusService {

    private final boolean enabled;
    private final String candidateId;
    private final boolean holdoutPassed;

    public ShadowModelStatusService(
            @Value("${herdsignal.shadow.enabled:false}") boolean enabled,
            @Value("${herdsignal.shadow.candidate-id:}") String candidateId,
            @Value("${herdsignal.shadow.holdout-passed:false}") boolean holdoutPassed
    ) {
        this.enabled = enabled;
        this.candidateId = candidateId == null ? "" : candidateId.trim();
        this.holdoutPassed = holdoutPassed;
    }

    public ShadowModelStatusResponse getStatus() {
        if (!enabled) {
            return response(
                    "DISABLED_RESEARCH_GATE_FAILED",
                    null,
                    "B0~B4가 사전 채택 기준을 통과하지 못해 shadow 계산을 시작하지 않습니다."
            );
        }
        if (!StringUtils.hasText(candidateId) || !holdoutPassed) {
            return response(
                    "BLOCKED_INVALID_CONFIGURATION",
                    StringUtils.hasText(candidateId) ? candidateId : null,
                    "후보 ID와 단일 Blind holdout 통과 기록이 모두 필요합니다."
            );
        }
        return response(
                "SHADOW_ACTIVE",
                candidateId,
                "운영 점수와 사용자 행동 응답에 반영하지 않고 병렬 관측만 수행합니다."
        );
    }

    private ShadowModelStatusResponse response(String status, String candidate, String reason) {
        return new ShadowModelStatusResponse(
                "HERD_v4 + HERD_v6.1 action",
                status,
                candidate,
                true,
                true,
                reason
        );
    }
}
