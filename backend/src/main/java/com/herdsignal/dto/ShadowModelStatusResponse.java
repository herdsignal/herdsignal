package com.herdsignal.dto;

/** 운영 HERD와 격리된 차세대 모델의 shadow 실행 상태. */
public record ShadowModelStatusResponse(
        String productionModel,
        String shadowStatus,
        String candidateId,
        boolean productionOutputUnaffected,
        boolean userActionSuppressed,
        String reason
) {
}
