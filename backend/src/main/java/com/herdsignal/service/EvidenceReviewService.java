package com.herdsignal.service;

import com.herdsignal.dto.EvidenceReviewResponse;
import com.herdsignal.dto.HerdObservationResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
@Slf4j
public class EvidenceReviewService {
    static final String SCOPE = "RESEARCH_EVIDENCE_REVIEW_ONLY";
    static final String NOTICE = "검증된 관찰 근거의 연구용 요약이며 매수·매도 추천이 아닙니다.";
    private static final Set<String> LENSES = Set.of(
            "HERD_STATE", "MARKET_CONTEXT", "RISK", "RED_TEAM"
    );

    private final HerdObservationService observationService;
    private final EvidenceReviewGateway gateway;
    private final CurrentUserService currentUserService;

    public EvidenceReviewResponse review(String ticker) {
        HerdObservationResponse observation = observationService.getLatest(ticker);
        List<EvidenceReviewResponse.EvidenceFact> facts = facts(observation);
        if (!"AVAILABLE".equals(observation.availabilityStatus())) {
            return unavailable("INSUFFICIENT_EVIDENCE", observation.ticker(), null, facts);
        }
        if (!gateway.isEnabled()) {
            return unavailable("DISABLED", observation.ticker(), observation.observationDate(), facts);
        }

        EvidenceReviewGateway.Packet packet = new EvidenceReviewGateway.Packet(
                observation.ticker(), SCOPE, facts
        );
        try {
            EvidenceReviewGateway.Draft draft = gateway.review(
                    packet,
                    safetyIdentifier(currentUserService.requireUserId())
            );
            validate(draft, facts);
            return new EvidenceReviewResponse(
                    "AVAILABLE", SCOPE, observation.ticker(), observation.observationDate(),
                    gateway.model(), List.copyOf(draft.lenses()), draft.summary(),
                    List.copyOf(draft.disagreements()), List.copyOf(draft.factsToVerify()),
                    facts, false, "HOLD", BigDecimal.ZERO, NOTICE
            );
        } catch (RuntimeException exception) {
            log.warn("AI evidence review rejected for {}: {}", observation.ticker(), exception.getMessage());
            return unavailable("PROVIDER_ERROR", observation.ticker(), observation.observationDate(), facts);
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
        Set<String> allowedIds = facts.stream()
                .map(EvidenceReviewResponse.EvidenceFact::id)
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
        Set<String> returnedLenses = draft.lenses().stream()
                .filter(java.util.Objects::nonNull)
                .map(EvidenceReviewResponse.Lens::code)
                .collect(java.util.stream.Collectors.toSet());
        if (!returnedLenses.equals(LENSES) || draft.lenses().size() != LENSES.size()) {
            throw new IllegalArgumentException("필수 근거 관점이 누락되거나 중복되었습니다.");
        }
        for (EvidenceReviewResponse.Lens lens : draft.lenses()) {
            if (lens == null || !LENSES.contains(lens.code()) || lens.evidenceIds() == null
                    || !allowedIds.containsAll(lens.evidenceIds())) {
                throw new IllegalArgumentException("허용되지 않은 관점 또는 근거 ID입니다.");
            }
        }
    }

    private List<EvidenceReviewResponse.EvidenceFact> facts(HerdObservationResponse row) {
        List<EvidenceReviewResponse.EvidenceFact> facts = new ArrayList<>();
        LocalDate asOf = row.observationDate();
        add(facts, "OBS.STATE_SCORE", "HERD 상태 점수", row.stateScore(), asOf, row.stateModelVersion());
        add(facts, "OBS.STAGE", "HERD 단계", row.stage(), asOf, row.stateModelVersion());
        add(facts, "OBS.TRANSITION", "상태 전이", row.transition(), asOf, row.transitionModelVersion());
        add(facts, "OBS.DELTA_4W", "4주 상태 변화", row.delta4w(), asOf, row.stateModelVersion());
        add(facts, "OBS.DELTA_13W", "13주 상태 변화", row.delta13w(), asOf, row.stateModelVersion());
        if (row.families() != null) {
            add(facts, "OBS.PRICE_EXTENSION", "가격 확장", row.families().priceExtension(), asOf, row.stateModelVersion());
            add(facts, "OBS.TREND_POSITION", "추세 위치", row.families().trendPosition(), asOf, row.stateModelVersion());
            add(facts, "OBS.RELATIVE_POSITION", "상대 위치", row.families().relativePosition(), asOf, row.stateModelVersion());
            add(facts, "OBS.PARTICIPATION", "참여", row.families().participation(), asOf, row.stateModelVersion());
        }
        add(facts, "OBS.DOWNSIDE_RISK", "하방 위험 맥락", row.downsideRiskContext(), asOf, row.stateModelVersion());
        add(facts, "OBS.SECTOR_ETF", "참조 섹터 ETF", row.sectorEtf(), asOf, row.stateModelVersion());
        return List.copyOf(facts);
    }

    private void add(List<EvidenceReviewResponse.EvidenceFact> facts, String id, String label,
                     Object value, LocalDate asOf, String source) {
        if (value != null) {
            facts.add(new EvidenceReviewResponse.EvidenceFact(id, label, String.valueOf(value), asOf, source));
        }
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
