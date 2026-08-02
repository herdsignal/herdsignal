package com.herdsignal.service.decision;

/** 검증 상태와 운용 검토를 섞지 않는 최종 판단 코드. */
public enum OperatingDecisionCode {
    INSUFFICIENT_DATA,
    OBSERVE,
    REVIEW_ADD,
    REVIEW_TRIM,
    THESIS_RISK,
    RISK_VETO
}
