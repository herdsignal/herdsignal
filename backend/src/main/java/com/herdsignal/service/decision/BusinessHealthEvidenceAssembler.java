package com.herdsignal.service.decision;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;

/** 기업 방향을 만들지 않고 SEC PIT 사실을 네 개의 장기 기업 관찰 축으로 묶는다. */
final class BusinessHealthEvidenceAssembler {
    private static final String ASSET_TYPE = "UNCLASSIFIED_US_LISTED";
    private static final int MAXIMUM_AGE_DAYS = 550;
    private static final Set<String> METRIC_IDS = Set.of(
            "BUSINESS.PIT.REVENUE_YOY",
            "BUSINESS.PIT.NET_MARGIN",
            "BUSINESS.PIT.NET_MARGIN_YOY_CHANGE",
            "BUSINESS.PIT.OPERATING_CASH_FLOW_YOY",
            "BUSINESS.PIT.LIABILITIES_TO_ASSETS",
            "BUSINESS.PIT.LIABILITIES_TO_ASSETS_YOY_CHANGE");

    BusinessHealthEvidenceBundle assemble(
            Optional<BusinessEvidenceSnapshot> candidate,
            LocalDate observationDate,
            OffsetDateTime generatedAt
    ) {
        Optional<BusinessEvidenceSnapshot> usable = candidate
                .filter(BusinessEvidenceSnapshot::usablePointInTimeFacts);
        if (usable.isEmpty()) {
            String reason = candidate.map(this::unavailableReason)
                    .orElse("검증된 ticker-CIK 기업 사실 범위에 포함되지 않습니다.");
            EvidenceFact fact = new EvidenceFact(
                    "BUSINESS.PIT", DecisionArea.BUSINESS_HEALTH, "SEC PIT 기업 사실",
                    reason, observationDate, generatedAt, "NOT_CONNECTED", "NONE",
                    ASSET_TYPE, EvidenceQuality.NO_VIEW, false, false, true, null);
            DecisionAreaAssessment assessment = new DecisionAreaAssessment(
                    DecisionArea.BUSINESS_HEALTH,
                    AssessmentStatus.NO_VIEW,
                    candidate.map(this::unavailableHeadline).orElse("SEC PIT 기업 사실 미연결"),
                    List.of(),
                    List.of("자료를 추정하거나 가격·HERD 값으로 대체하지 않습니다."));
            return new BusinessHealthEvidenceBundle(List.of(fact), assessment);
        }

        BusinessEvidenceSnapshot row = usable.orElseThrow();
        List<EvidenceFact> facts = facts(row);
        int availableMetrics = (int) facts.stream()
                .filter(fact -> METRIC_IDS.contains(fact.id()))
                .filter(fact -> fact.quality() == EvidenceQuality.AVAILABLE)
                .count();
        List<String> evidenceIds = facts.stream()
                .filter(fact -> fact.quality() == EvidenceQuality.AVAILABLE)
                .map(EvidenceFact::id)
                .toList();
        DecisionAreaAssessment assessment = new DecisionAreaAssessment(
                DecisionArea.BUSINESS_HEALTH,
                AssessmentStatus.PARTIAL,
                "SEC PIT 기업 사실 " + availableMetrics + "/" + METRIC_IDS.size() + " 확인",
                evidenceIds,
                List.of(
                        "성장·수익성·현금창출·재무구조의 원시 사실이며 종합 등급이 아닙니다.",
                        "기업 상태 방향·veto 가설은 OOS에서 탈락해 행동에 사용하지 않습니다.",
                        "마지막 SEC 접수: " + row.latestFactAcceptedAt().toLocalDate()));
        return new BusinessHealthEvidenceBundle(facts, assessment);
    }

    private List<EvidenceFact> facts(BusinessEvidenceSnapshot row) {
        List<EvidenceFact> facts = new ArrayList<>();
        add(facts, "BUSINESS.PIT.CIK", "SEC CIK", row.cik(), row);
        add(facts, "BUSINESS.PIT.FEATURE_MONTH", "재무 관찰 월", row.featureMonthEnd(), row);
        add(facts, "BUSINESS.PIT.REVENUE_YOY", "매출 전년 대비", row.revenueYoy(), row);
        add(facts, "BUSINESS.PIT.NET_MARGIN", "순이익률", row.netMargin(), row);
        add(facts, "BUSINESS.PIT.NET_MARGIN_YOY_CHANGE", "순이익률 전년 대비 변화",
                row.netMarginYoyChange(), row);
        add(facts, "BUSINESS.PIT.OPERATING_CASH_FLOW_YOY", "영업현금흐름 전년 대비",
                row.operatingCashFlowYoy(), row);
        add(facts, "BUSINESS.PIT.LIABILITIES_TO_ASSETS", "부채/자산",
                row.liabilitiesToAssets(), row);
        add(facts, "BUSINESS.PIT.LIABILITIES_TO_ASSETS_YOY_CHANGE", "부채/자산 전년 대비 변화",
                row.liabilitiesToAssetsYoyChange(), row);
        return List.copyOf(facts);
    }

    private void add(
            List<EvidenceFact> facts,
            String id,
            String label,
            Object value,
            BusinessEvidenceSnapshot row
    ) {
        OffsetDateTime acceptedAt = row.latestFactAcceptedAt();
        facts.add(new EvidenceFact(
                id,
                DecisionArea.BUSINESS_HEALTH,
                label,
                value == null ? null : value.toString(),
                acceptedAt.toLocalDate(),
                acceptedAt,
                "SEC_COMPANY_FACTS",
                row.sourceVersion(),
                ASSET_TYPE,
                value == null ? EvidenceQuality.NO_VIEW : EvidenceQuality.AVAILABLE,
                false,
                true,
                true,
                MAXIMUM_AGE_DAYS));
    }

    private String unavailableHeadline(BusinessEvidenceSnapshot row) {
        if (!"GENERAL".equals(row.entityType())) return row.entityType() + " 측정법 미지원";
        return "SEC PIT 기업 사실 사용 불가";
    }

    private String unavailableReason(BusinessEvidenceSnapshot row) {
        if (!"GENERAL".equals(row.entityType())) {
            return row.entityType() + " 전용 측정법이 검증되지 않았습니다.";
        }
        if (!"PIT_FACTS_READY".equals(row.corpusStatus())) {
            return "SEC 접수시각 연결이 완전하지 않습니다.";
        }
        return "사용 가능한 SEC 접수시각이 없습니다.";
    }
}
