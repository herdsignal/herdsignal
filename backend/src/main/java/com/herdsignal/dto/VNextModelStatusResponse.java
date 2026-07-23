package com.herdsignal.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * 차세대 HERD 연구 모델의 운영 경계.
 *
 * <p>연구 확률이나 가상 행동 비율을 사용자 행동으로 오인하지 않도록,
 * 채택 전에는 항상 HOLD와 0%만 반환한다.</p>
 */
public record VNextModelStatusResponse(
        String modelFamily,
        String lifecycle,
        String validationStatus,
        String decision,
        boolean sourceContractAccepted,
        boolean adoptableCandidate,
        String action,
        BigDecimal operationalActionRatio,
        boolean userActionSuppressed,
        String herdStateRole,
        String historicalRole,
        boolean survivorshipSafe,
        boolean blindHoldoutOpened,
        String prospectiveShadowStatus,
        String sourceReportVersion,
        String sourceSha256,
        List<String> promotionBlockers
) {
}
