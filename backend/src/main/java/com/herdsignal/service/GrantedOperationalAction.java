package com.herdsignal.service;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 승격 포트가 발급한 운영 행동 권한의 읽기 전용 계약.
 * sealed 타입이므로 승인 포트 밖에서 구현체를 만들 수 없다.
 */
public sealed interface GrantedOperationalAction
        permits AuditedOperationalActionPromotionPort.IssuedAction {

    String candidateId();

    String modelVersion();

    String ticker();

    String action();

    BigDecimal ratio();

    LocalDate asOfDate();
}
