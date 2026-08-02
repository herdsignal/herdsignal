package com.herdsignal.service.decision;

import java.time.OffsetDateTime;
import java.util.List;

/** 한 종목의 동일 판단 시점에 사용된 사실 집합. */
public record EvidencePacket(
        String schemaVersion,
        String ticker,
        String assetType,
        OffsetDateTime generatedAt,
        List<EvidenceFact> facts
) {
    public static final String SCHEMA_VERSION = "LONG_TERM_EVIDENCE_PACKET_V1";

    public EvidencePacket {
        facts = facts == null ? List.of() : List.copyOf(facts);
    }
}
