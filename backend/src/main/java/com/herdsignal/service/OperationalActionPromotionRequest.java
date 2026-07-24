package com.herdsignal.service;

import java.math.BigDecimal;
import java.time.LocalDate;

/** 검증 완료 모델이 운영 행동 권한을 요청할 때 사용하는 내부 계약. */
public record OperationalActionPromotionRequest(
        String candidateId,
        String modelVersion,
        String artifactSha256,
        String ticker,
        String action,
        BigDecimal ratio,
        LocalDate asOfDate
) {
}
