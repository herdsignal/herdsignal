package com.herdsignal.service.decision;

/** Evidence Packet에 포함되는 개별 사실의 사용 가능 상태. */
public enum EvidenceQuality {
    AVAILABLE,
    NO_VIEW,
    STALE,
    MISSING,
    INVALID
}
