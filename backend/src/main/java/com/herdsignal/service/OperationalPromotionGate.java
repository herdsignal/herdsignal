package com.herdsignal.service;

/** 연구 후보가 사람 검토까지 거쳐 운영 관측 또는 행동에 진입할 수 있는지 판정한다. */
public interface OperationalPromotionGate {
    boolean isApproved(String candidateId);
}
