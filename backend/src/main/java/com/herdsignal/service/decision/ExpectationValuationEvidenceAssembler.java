package com.herdsignal.service.decision;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** 원문 검수 가이던스만 표시하고 컨센서스·밸류를 추정하지 않는다. */
final class ExpectationValuationEvidenceAssembler {
    private static final String ASSET_TYPE = "UNCLASSIFIED_US_LISTED";
    private static final int MAXIMUM_AGE_DAYS = 550;
    private static final int MAXIMUM_FACTS = 8;

    ExpectationValuationEvidenceBundle assemble(
            List<GuidanceEvidenceFactSnapshot> candidates,
            LocalDate observationDate,
            OffsetDateTime generatedAt
    ) {
        List<GuidanceEvidenceFactSnapshot> guidance = latestEligibleAccession(
                candidates, observationDate, generatedAt.toLocalDate());
        List<EvidenceFact> facts = new ArrayList<>();
        guidance.forEach(row -> facts.add(guidanceFact(row)));
        facts.add(noView(
                "EXPECTATION.CONSENSUS", "애널리스트 컨센서스", observationDate, generatedAt,
                "시점 유효 컨센서스 원장이 연결되지 않았습니다."));
        facts.add(noView(
                "VALUATION.PIT", "시점 유효 밸류에이션", observationDate, generatedAt,
                "관찰일 기준 주가·주식수·재무 분모 원장이 연결되지 않았습니다."));

        if (guidance.isEmpty()) {
            facts.add(noView(
                    "EXPECTATION.GUIDANCE.PIT", "SEC 경영진 가이던스", observationDate, generatedAt,
                    "최근 550일 안의 검수 완료 가이던스 원문 사실이 없습니다."));
            return new ExpectationValuationEvidenceBundle(
                    facts,
                    new DecisionAreaAssessment(
                            DecisionArea.EXPECTATION_VALUATION,
                            AssessmentStatus.NO_VIEW,
                            "가이던스·컨센서스·밸류 미연결",
                            List.of(),
                            List.of("자료를 추정하거나 현재 PER로 과거 밸류를 대체하지 않습니다.")));
        }

        List<String> evidenceIds = facts.stream()
                .filter(fact -> fact.quality() == EvidenceQuality.AVAILABLE)
                .map(EvidenceFact::id)
                .toList();
        GuidanceEvidenceFactSnapshot latest = guidance.get(0);
        return new ExpectationValuationEvidenceBundle(
                facts,
                new DecisionAreaAssessment(
                        DecisionArea.EXPECTATION_VALUATION,
                        AssessmentStatus.PARTIAL,
                        "경영진 가이던스 원문 " + guidance.size() + "건 확인",
                        evidenceIds,
                        List.of(
                                "동일 accession의 지표·기간·범위 사실만 표시합니다.",
                                "상향·유지·하향 판정이 아닙니다.",
                                "애널리스트 컨센서스와 시점 유효 밸류에이션은 연결되지 않았습니다.",
                                "기대 변화 가설은 OOS에서 탈락해 행동에 사용하지 않습니다.",
                                "마지막 SEC 접수: " + latest.acceptedAt().toLocalDate())));
    }

    private List<GuidanceEvidenceFactSnapshot> latestEligibleAccession(
            List<GuidanceEvidenceFactSnapshot> candidates,
            LocalDate observationDate,
            LocalDate generatedDate
    ) {
        if (candidates == null || candidates.isEmpty()) return List.of();
        List<GuidanceEvidenceFactSnapshot> eligible = candidates.stream()
                .filter(row -> row.acceptedAt() != null)
                .filter(row -> !row.acceptedAt().toLocalDate().isAfter(observationDate))
                .filter(row -> {
                    long age = ChronoUnit.DAYS.between(
                            row.acceptedAt().toLocalDate(), generatedDate);
                    return age >= 0 && age <= MAXIMUM_AGE_DAYS;
                })
                .sorted(Comparator.comparing(GuidanceEvidenceFactSnapshot::acceptedAt).reversed())
                .toList();
        if (eligible.isEmpty()) return List.of();
        String accession = eligible.get(0).accessionNumber();
        return eligible.stream()
                .filter(row -> accession.equals(row.accessionNumber()))
                .sorted(Comparator.comparing(GuidanceEvidenceFactSnapshot::bindingId))
                .limit(MAXIMUM_FACTS)
                .toList();
    }

    private EvidenceFact guidanceFact(GuidanceEvidenceFactSnapshot row) {
        return new EvidenceFact(
                "EXPECTATION.GUIDANCE." + row.bindingId(),
                DecisionArea.EXPECTATION_VALUATION,
                row.metric() + " · " + row.fiscalPeriod() + " · " + row.accountingBasis(),
                guidanceValue(row),
                row.acceptedAt().toLocalDate(),
                row.acceptedAt(),
                "SEC_8K_EXHIBIT",
                row.sourceVersion() + ":" + row.sourceSha256(),
                ASSET_TYPE,
                EvidenceQuality.AVAILABLE,
                false,
                true,
                true,
                MAXIMUM_AGE_DAYS);
    }

    private EvidenceFact noView(
            String id,
            String label,
            LocalDate asOf,
            OffsetDateTime generatedAt,
            String reason
    ) {
        return new EvidenceFact(
                id, DecisionArea.EXPECTATION_VALUATION, label, reason, asOf, generatedAt,
                "NOT_CONNECTED", "NONE", ASSET_TYPE, EvidenceQuality.NO_VIEW,
                false, false, true, null);
    }

    private String guidanceValue(GuidanceEvidenceFactSnapshot row) {
        String lower = plain(row.lowerBound());
        String upper = plain(row.upperBound());
        String range = lower.equals(upper) ? lower : lower + "–" + upper;
        return range + " " + row.unit();
    }

    private String plain(BigDecimal value) {
        return value == null ? "—" : value.stripTrailingZeros().toPlainString();
    }
}
