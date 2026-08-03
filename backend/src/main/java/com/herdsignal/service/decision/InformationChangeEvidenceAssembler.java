package com.herdsignal.service.decision;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

/** 검증 또는 시점 요건을 통과하지 못한 비가격 자료를 운영 근거로 승격하지 않는다. */
final class InformationChangeEvidenceAssembler {
    private static final String ASSET_TYPE = "UNCLASSIFIED_US_LISTED";

    InformationChangeEvidenceBundle assemble(
            LocalDate observationDate,
            OffsetDateTime generatedAt
    ) {
        List<EvidenceFact> facts = List.of(
                noView(
                        "INFO.SEC.MATERIAL_EVENT",
                        "SEC 중요 사건",
                        observationDate,
                        generatedAt,
                        "8-K 중요 사건의 ticker–CIK 원문 검수가 완료되지 않았습니다."),
                noView(
                        "INFO.SEC.FORM4",
                        "내부자 거래",
                        observationDate,
                        generatedAt,
                        "Form 4 방향 가설이 독립 OOS에서 탈락해 운영 연결하지 않습니다."),
                noView(
                        "INFO.POSITIONING",
                        "공매도·기관 보유",
                        observationDate,
                        generatedAt,
                        "FINRA는 전향 관찰 전용이고 13F는 지연 맥락 자료라 운영 연결하지 않습니다."),
                noView(
                        "INFO.NEWS.PIT",
                        "중요 뉴스",
                        observationDate,
                        generatedAt,
                        "출처·게시시각·수정 이력이 고정된 뉴스 원장이 연결되지 않았습니다."));
        return new InformationChangeEvidenceBundle(
                facts,
                new DecisionAreaAssessment(
                        DecisionArea.INFORMATION_CHANGE,
                        AssessmentStatus.NO_VIEW,
                        "운영 연결 정보 변화 없음",
                        List.of(),
                        List.of(
                                "출처별 미연결 사유를 다른 영역의 값으로 대체하지 않습니다.",
                                "비가격 자료에서 방향·점수·행동 비율을 만들지 않습니다.")));
    }

    private EvidenceFact noView(
            String id,
            String label,
            LocalDate asOf,
            OffsetDateTime generatedAt,
            String reason
    ) {
        return new EvidenceFact(
                id,
                DecisionArea.INFORMATION_CHANGE,
                label,
                reason,
                asOf,
                generatedAt,
                "NOT_OPERATIONALLY_CONNECTED",
                "HERD_OPERATING_INFORMATION_CHANGE_EVIDENCE_V1",
                ASSET_TYPE,
                EvidenceQuality.NO_VIEW,
                false,
                false,
                true,
                null);
    }
}
