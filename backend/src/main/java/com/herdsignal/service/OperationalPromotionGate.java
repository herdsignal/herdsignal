package com.herdsignal.service;

import java.util.Optional;

/** 연구 후보가 사람 검토까지 거쳐 운영 관측 또는 행동에 진입할 수 있는지 판정한다. */
public interface OperationalPromotionGate {
    boolean isApproved(String candidateId);

    /**
     * 승격 포트가 모델 버전과 산출물 해시를 대조할 때 사용하는 근거.
     * 기존 단순 게이트 구현은 근거를 발급하지 않으므로 행동 승격에 사용할 수 없다.
     */
    default Optional<PromotionEvidence> approvalEvidence(String candidateId) {
        return Optional.empty();
    }
}
