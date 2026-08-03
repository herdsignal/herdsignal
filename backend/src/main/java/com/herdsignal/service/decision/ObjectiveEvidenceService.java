package com.herdsignal.service.decision;

import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.service.HerdObservationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** State S1을 객관적 판단 영역으로 옮기되 미구현 근거를 추정하지 않는다. */
@Service
public class ObjectiveEvidenceService {
    private static final String ASSET_TYPE = "UNCLASSIFIED_US_LISTED";
    private static final int STATE_MAXIMUM_AGE_DAYS = 10;
    private static final int BUSINESS_MAXIMUM_AGE_DAYS = 550;

    private final HerdObservationService observationService;
    private final EvidenceGate evidenceGate;
    private final PitBusinessEvidenceProvider businessEvidenceProvider;
    private final Clock clock;

    @Autowired
    public ObjectiveEvidenceService(
            HerdObservationService observationService,
            EvidenceGate evidenceGate,
            PitBusinessEvidenceProvider businessEvidenceProvider
    ) {
        this(observationService, evidenceGate, businessEvidenceProvider, Clock.systemUTC());
    }

    ObjectiveEvidenceService(
            HerdObservationService observationService,
            EvidenceGate evidenceGate,
            Clock clock
    ) {
        this(observationService, evidenceGate, (ticker, date) -> Optional.empty(), clock);
    }

    ObjectiveEvidenceService(
            HerdObservationService observationService,
            EvidenceGate evidenceGate,
            PitBusinessEvidenceProvider businessEvidenceProvider,
            Clock clock
    ) {
        this.observationService = observationService;
        this.evidenceGate = evidenceGate;
        this.businessEvidenceProvider = businessEvidenceProvider;
        this.clock = clock;
    }

    public ObjectiveReviewResponse review(String ticker) {
        HerdObservationResponse observation = observationService.getLatest(ticker);
        OffsetDateTime generatedAt = OffsetDateTime.now(clock).withOffsetSameInstant(ZoneOffset.UTC);
        LocalDate observationDate = observation.observationDate() == null
                ? generatedAt.toLocalDate()
                : observation.observationDate();
        Optional<BusinessEvidenceSnapshot> business = businessEvidenceProvider.latestAsOf(
                observation.ticker(), observationDate);
        List<EvidenceFact> facts = facts(observation, business, generatedAt);
        EvidencePacket packet = new EvidencePacket(
                EvidencePacket.SCHEMA_VERSION,
                observation.ticker(),
                ASSET_TYPE,
                generatedAt,
                facts
        );
        EvidenceGateResult gate = evidenceGate.evaluate(packet);
        return new ObjectiveReviewResponse(
                gate.open() ? "AVAILABLE" : "INSUFFICIENT_DATA",
                observation.ticker(),
                packet,
                gate,
                assessments(observation, business, facts, gate),
                false,
                "OBSERVE",
                0.0
        );
    }

    private List<EvidenceFact> facts(
            HerdObservationResponse row,
            Optional<BusinessEvidenceSnapshot> business,
            OffsetDateTime generatedAt
    ) {
        LocalDate asOf = row.observationDate() == null
                ? generatedAt.toLocalDate()
                : row.observationDate();
        OffsetDateTime observedAt = row.generatedAt() == null ? generatedAt : row.generatedAt();
        boolean available = "AVAILABLE".equals(row.availabilityStatus());
        EvidenceQuality stateQuality = available && "FRESH".equals(row.freshnessStatus())
                ? EvidenceQuality.AVAILABLE
                : available ? EvidenceQuality.STALE : EvidenceQuality.MISSING;
        List<EvidenceFact> facts = new ArrayList<>();
        add(facts, "OBS.STATE_SCORE", DecisionArea.CHART_CROWD, "HERD 상태 점수",
                row.stateScore(), asOf, observedAt, row.stateModelVersion(), stateQuality, true);
        add(facts, "OBS.STAGE", DecisionArea.CHART_CROWD, "HERD 단계",
                row.stage(), asOf, observedAt, row.stateModelVersion(), stateQuality, true);
        add(facts, "OBS.TRANSITION", DecisionArea.CHART_CROWD, "HERD 전이",
                row.transition(), asOf, observedAt, row.transitionModelVersion(), stateQuality, true);
        addOptional(facts, "OBS.DELTA_4W", DecisionArea.CHART_CROWD, "4주 변화",
                row.delta4w(), asOf, observedAt, row.stateModelVersion(), stateQuality);
        addOptional(facts, "OBS.DELTA_13W", DecisionArea.CHART_CROWD, "13주 변화",
                row.delta13w(), asOf, observedAt, row.stateModelVersion(), stateQuality);
        if (row.families() != null) {
            addOptional(facts, "OBS.PRICE_EXTENSION", DecisionArea.CHART_CROWD, "가격 확장",
                    row.families().priceExtension(), asOf, observedAt, row.stateModelVersion(), stateQuality);
            addOptional(facts, "OBS.TREND_POSITION", DecisionArea.CHART_CROWD, "추세 위치",
                    row.families().trendPosition(), asOf, observedAt, row.stateModelVersion(), stateQuality);
            addOptional(facts, "OBS.RELATIVE_POSITION", DecisionArea.CHART_CROWD, "상대 위치",
                    row.families().relativePosition(), asOf, observedAt, row.stateModelVersion(), stateQuality);
            addOptional(facts, "OBS.PARTICIPATION", DecisionArea.CHART_CROWD, "참여",
                    row.families().participation(), asOf, observedAt, row.stateModelVersion(), stateQuality);
        }
        addOptional(facts, "OBS.DOWNSIDE_RISK", DecisionArea.CHART_CROWD, "하방 위험 맥락",
                row.downsideRiskContext(), asOf, observedAt, row.stateModelVersion(), stateQuality);
        addOptional(facts, "OBS.SECTOR_REFERENCE", DecisionArea.MARKET_SECTOR, "참조 섹터 ETF",
                row.sectorEtf(), asOf, observedAt, row.stateModelVersion(), stateQuality);

        if (business.filter(BusinessEvidenceSnapshot::usablePointInTimeFacts).isPresent()) {
            addBusinessFacts(facts, business.orElseThrow());
        } else {
            noView(facts, "BUSINESS.PIT", DecisionArea.BUSINESS_HEALTH,
                    "SEC PIT 기업 사실", asOf, generatedAt,
                    business.map(this::businessUnavailableReason)
                            .orElse("검증된 ticker-CIK 기업 사실 범위에 포함되지 않습니다."));
        }
        noView(facts, "VALUATION.PIT", DecisionArea.EXPECTATION_VALUATION,
                "PIT 기대·가격", asOf, generatedAt,
                "검증된 기대·가격 근거가 아직 연결되지 않았습니다.");
        noView(facts, "MARKET.REGIME", DecisionArea.MARKET_SECTOR,
                "독립 시장·섹터 국면", asOf, generatedAt,
                "State S1 입력과 중복되지 않는 독립 국면 출력이 아직 없습니다.");
        noView(facts, "INFO.CHANGE", DecisionArea.INFORMATION_CHANGE,
                "확인된 정보 변화", asOf, generatedAt,
                "운영 방향 권한을 가진 비가격 정보가 없습니다.");
        return List.copyOf(facts);
    }

    private List<DecisionAreaAssessment> assessments(
            HerdObservationResponse row,
            Optional<BusinessEvidenceSnapshot> business,
            List<EvidenceFact> facts,
            EvidenceGateResult gate
    ) {
        List<String> chartIds = ids(facts, DecisionArea.CHART_CROWD, EvidenceQuality.AVAILABLE);
        List<String> marketIds = ids(facts, DecisionArea.MARKET_SECTOR, EvidenceQuality.AVAILABLE);
        List<String> businessIds = ids(facts, DecisionArea.BUSINESS_HEALTH, EvidenceQuality.AVAILABLE);
        DecisionAreaAssessment businessAssessment = business
                .filter(BusinessEvidenceSnapshot::usablePointInTimeFacts)
                .map(snapshot -> new DecisionAreaAssessment(
                        DecisionArea.BUSINESS_HEALTH,
                        AssessmentStatus.PARTIAL,
                        "SEC PIT 재무 사실 확인",
                        businessIds,
                        List.of(
                                "기업 상태 방향·veto 가설은 OOS에서 탈락해 행동에 사용하지 않습니다.",
                                "마지막 SEC 접수: " + snapshot.latestFactAcceptedAt().toLocalDate())))
                .orElseGet(() -> noViewAssessment(
                        DecisionArea.BUSINESS_HEALTH,
                        business.map(this::businessUnavailableHeadline)
                                .orElse("SEC PIT 기업 사실 미연결")));
        return List.of(
                businessAssessment,
                noViewAssessment(DecisionArea.EXPECTATION_VALUATION, "기대·가격 모델 연결 전"),
                new DecisionAreaAssessment(
                        DecisionArea.MARKET_SECTOR,
                        marketIds.isEmpty() ? AssessmentStatus.NO_VIEW : AssessmentStatus.PARTIAL,
                        marketIds.isEmpty() ? "독립 시장·섹터 근거 없음" : "섹터 참조만 확인",
                        marketIds,
                        List.of("시장 국면과 섹터 방향을 별도 계산하지 않았습니다.")),
                new DecisionAreaAssessment(
                        DecisionArea.CHART_CROWD,
                        gate.open() ? AssessmentStatus.AVAILABLE : AssessmentStatus.BLOCKED,
                        gate.open() ? chartHeadline(row) : "HERD 관찰값 사용 불가",
                        chartIds,
                        gate.open() ? List.of("상태 설명이며 행동 방향 근거가 아닙니다.") : gate.reasons()),
                noViewAssessment(DecisionArea.INFORMATION_CHANGE, "검증된 운영 정보 변화 없음")
        );
    }

    private DecisionAreaAssessment noViewAssessment(DecisionArea area, String headline) {
        return new DecisionAreaAssessment(area, AssessmentStatus.NO_VIEW, headline, List.of(),
                List.of("자료를 추정하거나 다른 영역의 값으로 대체하지 않습니다."));
    }

    private String chartHeadline(HerdObservationResponse row) {
        String stage = row.stage() == null ? "단계 미확인" : row.stage();
        String transition = row.transition() == null ? "전이 미확인" : row.transition();
        return stage + " · " + transition;
    }

    private List<String> ids(
            List<EvidenceFact> facts,
            DecisionArea area,
            EvidenceQuality quality
    ) {
        return facts.stream()
                .filter(fact -> fact.area() == area && fact.quality() == quality)
                .map(EvidenceFact::id)
                .toList();
    }

    private void add(
            List<EvidenceFact> facts,
            String id,
            DecisionArea area,
            String label,
            Object value,
            LocalDate asOf,
            OffsetDateTime observedAt,
            String sourceVersion,
            EvidenceQuality quality,
            boolean required
    ) {
        EvidenceQuality resolved = value == null && required ? EvidenceQuality.MISSING : quality;
        facts.add(new EvidenceFact(
                id, area, label, value == null ? null : value.toString(), asOf, observedAt,
                "HERD_OBSERVATION", defaultVersion(sourceVersion), ASSET_TYPE,
                resolved, required, false, true, STATE_MAXIMUM_AGE_DAYS));
    }

    private void addOptional(
            List<EvidenceFact> facts,
            String id,
            DecisionArea area,
            String label,
            Object value,
            LocalDate asOf,
            OffsetDateTime observedAt,
            String sourceVersion,
            EvidenceQuality baseQuality
    ) {
        EvidenceQuality quality = value == null ? EvidenceQuality.NO_VIEW : baseQuality;
        add(facts, id, area, label, value, asOf, observedAt, sourceVersion, quality, false);
    }

    private void noView(
            List<EvidenceFact> facts,
            String id,
            DecisionArea area,
            String label,
            LocalDate asOf,
            OffsetDateTime observedAt,
            String reason
    ) {
        facts.add(new EvidenceFact(
                id, area, label, reason, asOf, observedAt,
                "NOT_CONNECTED", "NONE", ASSET_TYPE, EvidenceQuality.NO_VIEW,
                false, false, true, null));
    }

    private void addBusinessFacts(
            List<EvidenceFact> facts,
            BusinessEvidenceSnapshot row
    ) {
        OffsetDateTime acceptedAt = row.latestFactAcceptedAt();
        LocalDate asOf = acceptedAt.toLocalDate();
        String sourceVersion = row.sourceVersion();
        addBusinessFact(facts, "BUSINESS.PIT.CIK", "SEC CIK", row.cik(), asOf, acceptedAt, sourceVersion);
        addBusinessFact(facts, "BUSINESS.PIT.FEATURE_MONTH", "재무 관찰 월",
                row.featureMonthEnd(), asOf, acceptedAt, sourceVersion);
        addBusinessMetric(facts, "BUSINESS.PIT.REVENUE_YOY", "매출 전년 대비",
                row.revenueYoy(), asOf, acceptedAt, sourceVersion);
        addBusinessMetric(facts, "BUSINESS.PIT.NET_MARGIN", "순이익률",
                row.netMargin(), asOf, acceptedAt, sourceVersion);
        addBusinessMetric(facts, "BUSINESS.PIT.NET_MARGIN_YOY_CHANGE", "순이익률 전년 대비 변화",
                row.netMarginYoyChange(), asOf, acceptedAt, sourceVersion);
        addBusinessMetric(facts, "BUSINESS.PIT.OPERATING_CASH_FLOW_YOY", "영업현금흐름 전년 대비",
                row.operatingCashFlowYoy(), asOf, acceptedAt, sourceVersion);
        addBusinessMetric(facts, "BUSINESS.PIT.LIABILITIES_TO_ASSETS", "부채/자산",
                row.liabilitiesToAssets(), asOf, acceptedAt, sourceVersion);
        addBusinessMetric(facts, "BUSINESS.PIT.LIABILITIES_TO_ASSETS_YOY_CHANGE", "부채/자산 전년 대비 변화",
                row.liabilitiesToAssetsYoyChange(), asOf, acceptedAt, sourceVersion);
    }

    private void addBusinessMetric(
            List<EvidenceFact> facts,
            String id,
            String label,
            BigDecimal value,
            LocalDate asOf,
            OffsetDateTime acceptedAt,
            String sourceVersion
    ) {
        addBusinessFact(facts, id, label, value, asOf, acceptedAt, sourceVersion);
    }

    private void addBusinessFact(
            List<EvidenceFact> facts,
            String id,
            String label,
            Object value,
            LocalDate asOf,
            OffsetDateTime acceptedAt,
            String sourceVersion
    ) {
        facts.add(new EvidenceFact(
                id,
                DecisionArea.BUSINESS_HEALTH,
                label,
                value == null ? null : value.toString(),
                asOf,
                acceptedAt,
                "SEC_COMPANY_FACTS",
                sourceVersion,
                ASSET_TYPE,
                value == null ? EvidenceQuality.NO_VIEW : EvidenceQuality.AVAILABLE,
                false,
                true,
                true,
                BUSINESS_MAXIMUM_AGE_DAYS));
    }

    private String businessUnavailableHeadline(BusinessEvidenceSnapshot row) {
        if (!"GENERAL".equals(row.entityType())) return row.entityType() + " 측정법 미지원";
        return "SEC PIT 기업 사실 사용 불가";
    }

    private String businessUnavailableReason(BusinessEvidenceSnapshot row) {
        if (!"GENERAL".equals(row.entityType())) {
            return row.entityType() + " 전용 측정법이 검증되지 않았습니다.";
        }
        if (!"PIT_FACTS_READY".equals(row.corpusStatus())) {
            return "SEC 접수시각 연결이 완전하지 않습니다.";
        }
        return "사용 가능한 SEC 접수시각이 없습니다.";
    }

    private String defaultVersion(String version) {
        return version == null || version.isBlank() ? "UNKNOWN" : version;
    }
}
