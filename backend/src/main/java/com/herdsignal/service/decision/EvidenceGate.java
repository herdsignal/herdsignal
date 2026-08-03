package com.herdsignal.service.decision;

import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** 누락·노후·시점 위반이 있는 필수 사실을 fail-closed로 차단한다. */
@Component
public class EvidenceGate {

    public EvidenceGateResult evaluate(EvidencePacket packet) {
        List<String> reasons = new ArrayList<>();
        if (packet == null) {
            return blocked("PACKET_MISSING");
        }
        requiredText(packet.schemaVersion(), "SCHEMA_VERSION_MISSING", reasons);
        if (!EvidencePacket.SCHEMA_VERSION.equals(packet.schemaVersion())) {
            reasons.add("SCHEMA_VERSION_UNSUPPORTED");
        }
        requiredText(packet.ticker(), "TICKER_MISSING", reasons);
        requiredText(packet.assetType(), "ASSET_TYPE_MISSING", reasons);
        if (packet.generatedAt() == null) {
            reasons.add("GENERATED_AT_MISSING");
        }
        if (packet.facts().isEmpty()) {
            reasons.add("FACTS_MISSING");
        }

        Set<String> ids = new HashSet<>();
        for (EvidenceFact fact : packet.facts()) {
            validateFact(fact, packet, ids, reasons);
        }
        return reasons.isEmpty()
                ? new EvidenceGateResult(EvidenceGateResult.Status.OPEN, List.of())
                : new EvidenceGateResult(EvidenceGateResult.Status.BLOCKED, reasons);
    }

    private void validateFact(
            EvidenceFact fact,
            EvidencePacket packet,
            Set<String> ids,
            List<String> reasons
    ) {
        if (fact == null) {
            reasons.add("FACT_NULL");
            return;
        }
        String prefix = fact.id() == null || fact.id().isBlank() ? "FACT" : fact.id();
        requiredText(fact.id(), prefix + ":ID_MISSING", reasons);
        if (fact.id() != null && !ids.add(fact.id())) {
            reasons.add(prefix + ":ID_DUPLICATED");
        }
        if (fact.area() == null) reasons.add(prefix + ":AREA_MISSING");
        if (fact.area() == DecisionArea.MARKET_SECTOR
                && ("HERD_OBSERVATION".equals(fact.source()) || prefix.startsWith("OBS."))) {
            reasons.add(prefix + ":MARKET_SECTOR_NOT_INDEPENDENT");
        }
        requiredText(fact.label(), prefix + ":LABEL_MISSING", reasons);
        requiredText(fact.source(), prefix + ":SOURCE_MISSING", reasons);
        requiredText(fact.sourceVersion(), prefix + ":SOURCE_VERSION_MISSING", reasons);
        requiredText(fact.assetType(), prefix + ":ASSET_TYPE_MISSING", reasons);
        if (packet.assetType() != null && fact.assetType() != null
                && !packet.assetType().equals(fact.assetType())) {
            reasons.add(prefix + ":ASSET_TYPE_MISMATCH");
        }
        if (fact.asOfDate() == null) reasons.add(prefix + ":AS_OF_DATE_MISSING");
        if (fact.observedAt() == null) reasons.add(prefix + ":OBSERVED_AT_MISSING");
        if (fact.quality() == null) reasons.add(prefix + ":QUALITY_MISSING");
        if (fact.requiredForDecision() && fact.quality() != EvidenceQuality.AVAILABLE) {
            reasons.add(prefix + ":REQUIRED_FACT_UNAVAILABLE");
        }
        if (fact.pointInTimeRequired() && !fact.pointInTimeValid()) {
            reasons.add(prefix + ":PIT_INVALID");
        }
        if (packet.generatedAt() != null && fact.asOfDate() != null) {
            LocalDate generatedDate = packet.generatedAt().toLocalDate();
            if (fact.asOfDate().isAfter(generatedDate)) {
                reasons.add(prefix + ":FUTURE_AS_OF_DATE");
            } else if (fact.maximumAgeDays() != null && fact.maximumAgeDays() >= 0
                    && ChronoUnit.DAYS.between(fact.asOfDate(), generatedDate) > fact.maximumAgeDays()) {
                reasons.add(prefix + ":STALE_BY_AGE");
            }
        }
        if (packet.generatedAt() != null && fact.observedAt() != null
                && fact.observedAt().isAfter(packet.generatedAt())) {
            reasons.add(prefix + ":FUTURE_OBSERVED_AT");
        }
    }

    private void requiredText(String value, String reason, List<String> reasons) {
        if (value == null || value.isBlank()) reasons.add(reason);
    }

    private EvidenceGateResult blocked(String reason) {
        return new EvidenceGateResult(EvidenceGateResult.Status.BLOCKED, List.of(reason));
    }
}
