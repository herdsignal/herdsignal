package com.herdsignal.service;

import java.util.Optional;

/** 검증된 방향 모델이 사용자 행동 경계로 들어오는 유일한 내부 포트. */
public interface OperationalActionPromotionPort {
    Optional<GrantedOperationalAction> request(
            OperationalActionPromotionRequest request
    );
}
