package com.herdsignal.service;

import com.herdsignal.dto.EvidenceReviewResponse;
import com.herdsignal.service.decision.DecisionArea;
import com.herdsignal.service.decision.EvidenceFact;
import com.herdsignal.service.decision.EvidencePacket;
import com.herdsignal.service.decision.EvidenceQuality;
import com.herdsignal.service.decision.ObjectiveEvidenceService;
import com.herdsignal.service.decision.ObjectiveReviewResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.Collections;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class EvidenceReviewService {
    static final String SCOPE = "LONG_TERM_REVIEW_EVIDENCE_ONLY";
    static final String NOTICE = "검증된 관찰 근거의 연구용 요약이며 매수·매도 추천이 아닙니다.";
    private static final String RED_TEAM = "RED_TEAM";
    private static final Map<String, DecisionArea> AREA_LENSES = areaLenses();
    private static final Set<String> LENSES = java.util.stream.Stream.concat(
                    AREA_LENSES.keySet().stream(), java.util.stream.Stream.of(RED_TEAM))
            .collect(Collectors.toUnmodifiableSet());

    private final ObjectiveEvidenceService objectiveEvidenceService;
    private final EvidenceReviewGateway gateway;
    private final CurrentUserService currentUserService;

    public EvidenceReviewResponse review(String ticker) {
        ObjectiveReviewResponse objective = objectiveEvidenceService.review(ticker);
        List<EvidenceReviewResponse.EvidenceFact> facts = facts(objective.evidencePacket());
        LocalDate asOf = observationDate(objective.evidencePacket());
        if (!objective.dataGate().open()) {
            return unavailable("INSUFFICIENT_EVIDENCE", objective.ticker(), asOf, facts);
        }
        if (!gateway.isEnabled()) {
            return unavailable("DISABLED", objective.ticker(), asOf, facts);
        }

        EvidenceReviewGateway.Packet packet = new EvidenceReviewGateway.Packet(
                objective.ticker(), SCOPE, facts
        );
        try {
            EvidenceReviewGateway.Draft draft = gateway.review(
                    packet,
                    safetyIdentifier(currentUserService.requireUserId())
            );
            validate(draft, facts);
            return new EvidenceReviewResponse(
                    "AVAILABLE", SCOPE, objective.ticker(), asOf,
                    gateway.model(), List.copyOf(draft.lenses()), draft.summary(),
                    List.copyOf(draft.disagreements()), List.copyOf(draft.factsToVerify()),
                    facts, false, "HOLD", BigDecimal.ZERO, NOTICE
            );
        } catch (RuntimeException exception) {
            log.warn(
                    "AI evidence review rejected for {}: {}",
                    objective.ticker(), exception.getMessage()
            );
            return unavailable("PROVIDER_ERROR", objective.ticker(), asOf, facts);
        }
    }

    private void validate(
            EvidenceReviewGateway.Draft draft,
            List<EvidenceReviewResponse.EvidenceFact> facts
    ) {
        if (draft == null || draft.lenses() == null || draft.summary() == null
                || draft.disagreements() == null || draft.factsToVerify() == null) {
            throw new IllegalArgumentException("불완전한 AI 근거 분석 응답입니다.");
        }
        if (draft.directionPrediction()
                || !"HOLD".equals(draft.operationalAction())
                || Double.compare(draft.operationalActionRatio(), 0.0) != 0) {
            throw new IllegalArgumentException("AI 근거 분석은 행동 권한을 가질 수 없습니다.");
        }
        Map<String, EvidenceReviewResponse.EvidenceFact> allowedFacts = facts.stream()
                .collect(Collectors.toUnmodifiableMap(
                        EvidenceReviewResponse.EvidenceFact::id,
                        fact -> fact
                ));
        Set<String> allowedIds = allowedFacts.keySet();
        Set<String> returnedLenses = draft.lenses().stream()
                .filter(java.util.Objects::nonNull)
                .map(EvidenceReviewResponse.Lens::code)
                .collect(java.util.stream.Collectors.toSet());
        if (!returnedLenses.equals(LENSES) || draft.lenses().size() != LENSES.size()) {
            throw new IllegalArgumentException("필수 근거 관점이 누락되거나 중복되었습니다.");
        }
        for (EvidenceReviewResponse.Lens lens : draft.lenses()) {
            if (lens == null || !LENSES.contains(lens.code()) || lens.evidenceIds() == null
                    || lens.missingEvidence() == null || lens.summary() == null
                    || lens.summary().isBlank() || !allowedIds.containsAll(lens.evidenceIds())) {
                throw new IllegalArgumentException("허용되지 않은 관점 또는 근거 ID입니다.");
            }
            validateLensEvidence(lens, allowedFacts);
        }
    }

    private void validateLensEvidence(
            EvidenceReviewResponse.Lens lens,
            Map<String, EvidenceReviewResponse.EvidenceFact> facts
    ) {
        if (RED_TEAM.equals(lens.code())) {
            boolean citesUnavailable = lens.evidenceIds().stream()
                    .map(facts::get)
                    .anyMatch(fact -> !EvidenceQuality.AVAILABLE.name().equals(fact.quality()));
            if (citesUnavailable) {
                throw new IllegalArgumentException("반대 검증이 사용 불가 근거를 인용했습니다.");
            }
            if (lens.evidenceIds().isEmpty() && lens.missingEvidence().isEmpty()) {
                throw new IllegalArgumentException("반대 검증에는 근거나 누락 항목이 필요합니다.");
            }
            return;
        }
        DecisionArea expectedArea = AREA_LENSES.get(lens.code());
        boolean crossedBoundary = lens.evidenceIds().stream()
                .map(facts::get)
                .anyMatch(fact -> !expectedArea.name().equals(fact.area()));
        if (crossedBoundary) {
            throw new IllegalArgumentException("판단 영역 사이의 근거가 혼용되었습니다.");
        }
        boolean citesUnavailable = lens.evidenceIds().stream()
                .map(facts::get)
                .anyMatch(fact -> !EvidenceQuality.AVAILABLE.name().equals(fact.quality()));
        if (citesUnavailable) {
            throw new IllegalArgumentException("사용 불가 근거가 인용되었습니다.");
        }
        boolean hasAvailableFact = facts.values().stream()
                .anyMatch(fact -> expectedArea.name().equals(fact.area())
                        && EvidenceQuality.AVAILABLE.name().equals(fact.quality()));
        if (hasAvailableFact && lens.evidenceIds().isEmpty()) {
            throw new IllegalArgumentException("사용 가능한 영역 근거가 인용되지 않았습니다.");
        }
        if (!hasAvailableFact && lens.missingEvidence().isEmpty()) {
            throw new IllegalArgumentException("근거가 없는 영역의 누락 사실이 표시되지 않았습니다.");
        }
    }

    private List<EvidenceReviewResponse.EvidenceFact> facts(EvidencePacket packet) {
        if (packet == null || packet.facts() == null) {
            return List.of();
        }
        return packet.facts().stream()
                .map(fact -> new EvidenceReviewResponse.EvidenceFact(
                        fact.id(), fact.area().name(), fact.label(), fact.value(),
                        fact.asOfDate(), fact.observedAt(), fact.source(), fact.sourceVersion(),
                        fact.quality().name()))
                .toList();
    }

    private LocalDate observationDate(EvidencePacket packet) {
        if (packet == null) return null;
        return packet.facts().stream()
                .filter(fact -> "OBS.STATE_SCORE".equals(fact.id()))
                .map(EvidenceFact::asOfDate)
                .findFirst()
                .orElse(packet.generatedAt() == null ? null : packet.generatedAt().toLocalDate());
    }

    private static Map<String, DecisionArea> areaLenses() {
        LinkedHashMap<String, DecisionArea> result = new LinkedHashMap<>();
        result.put("BUSINESS_HEALTH", DecisionArea.BUSINESS_HEALTH);
        result.put("EXPECTATION_VALUATION", DecisionArea.EXPECTATION_VALUATION);
        result.put("MARKET_SECTOR", DecisionArea.MARKET_SECTOR);
        result.put("CHART_CROWD", DecisionArea.CHART_CROWD);
        result.put("INFORMATION_CHANGE", DecisionArea.INFORMATION_CHANGE);
        return Collections.unmodifiableMap(result);
    }

    private EvidenceReviewResponse unavailable(
            String status, String ticker, LocalDate asOf,
            List<EvidenceReviewResponse.EvidenceFact> facts
    ) {
        return new EvidenceReviewResponse(
                status, SCOPE, ticker, asOf, gateway.model(), List.of(), null,
                List.of(), List.of(), facts, false, "HOLD", BigDecimal.ZERO, NOTICE
        );
    }

    private String safetyIdentifier(String userId) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(userId.getBytes(StandardCharsets.UTF_8));
            return "hs_" + HexFormat.of().formatHex(digest, 0, 12);
        } catch (Exception exception) {
            throw new IllegalStateException("safety identifier 생성 실패", exception);
        }
    }
}
