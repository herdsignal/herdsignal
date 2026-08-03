package com.herdsignal.service.decision;

import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.service.HerdObservationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

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

    private final HerdObservationService observationService;
    private final EvidenceGate evidenceGate;
    private final PitBusinessEvidenceProvider businessEvidenceProvider;
    private final PitGuidanceEvidenceProvider guidanceEvidenceProvider;
    private final MarketSectorEvidenceProvider marketSectorEvidenceProvider;
    private final BusinessHealthEvidenceAssembler businessHealthEvidenceAssembler =
            new BusinessHealthEvidenceAssembler();
    private final ExpectationValuationEvidenceAssembler expectationValuationEvidenceAssembler =
            new ExpectationValuationEvidenceAssembler();
    private final Clock clock;

    @Autowired
    public ObjectiveEvidenceService(
            HerdObservationService observationService,
            EvidenceGate evidenceGate,
            PitBusinessEvidenceProvider businessEvidenceProvider,
            PitGuidanceEvidenceProvider guidanceEvidenceProvider,
            MarketSectorEvidenceProvider marketSectorEvidenceProvider
    ) {
        this(observationService, evidenceGate, businessEvidenceProvider,
                guidanceEvidenceProvider, marketSectorEvidenceProvider, Clock.systemUTC());
    }

    ObjectiveEvidenceService(
            HerdObservationService observationService,
            EvidenceGate evidenceGate,
            Clock clock
    ) {
        this(observationService, evidenceGate, (ticker, date) -> Optional.empty(),
                (ticker, date) -> List.of(), (ticker, sector, date) -> Optional.empty(), clock);
    }

    ObjectiveEvidenceService(
            HerdObservationService observationService,
            EvidenceGate evidenceGate,
            PitBusinessEvidenceProvider businessEvidenceProvider,
            Clock clock
    ) {
        this(observationService, evidenceGate, businessEvidenceProvider,
                (ticker, date) -> List.of(), (ticker, sector, date) -> Optional.empty(), clock);
    }

    ObjectiveEvidenceService(
            HerdObservationService observationService,
            EvidenceGate evidenceGate,
            PitBusinessEvidenceProvider businessEvidenceProvider,
            PitGuidanceEvidenceProvider guidanceEvidenceProvider,
            Clock clock
    ) {
        this(observationService, evidenceGate, businessEvidenceProvider,
                guidanceEvidenceProvider, (ticker, sector, date) -> Optional.empty(), clock);
    }

    ObjectiveEvidenceService(
            HerdObservationService observationService,
            EvidenceGate evidenceGate,
            PitBusinessEvidenceProvider businessEvidenceProvider,
            PitGuidanceEvidenceProvider guidanceEvidenceProvider,
            MarketSectorEvidenceProvider marketSectorEvidenceProvider,
            Clock clock
    ) {
        this.observationService = observationService;
        this.evidenceGate = evidenceGate;
        this.businessEvidenceProvider = businessEvidenceProvider;
        this.guidanceEvidenceProvider = guidanceEvidenceProvider;
        this.marketSectorEvidenceProvider = marketSectorEvidenceProvider;
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
        BusinessHealthEvidenceBundle businessHealth = businessHealthEvidenceAssembler.assemble(
                business, observationDate, generatedAt);
        ExpectationValuationEvidenceBundle expectationValuation =
                expectationValuationEvidenceAssembler.assemble(
                        guidanceEvidenceProvider.latestAccessionAsOf(
                                observation.ticker(), observationDate),
                        observationDate,
                        generatedAt);
        Optional<MarketSectorEvidenceSnapshot> marketSector = marketSectorEvidenceProvider.contextAsOf(
                observation.ticker(), observation.sectorEtf(), observationDate);
        List<EvidenceFact> facts = facts(
                observation, businessHealth, expectationValuation, marketSector, generatedAt);
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
                assessments(
                        observation,
                        businessHealth.assessment(),
                        expectationValuation.assessment(),
                        marketSector,
                        facts,
                        gate),
                false,
                "OBSERVE",
                0.0
        );
    }

    private List<EvidenceFact> facts(
            HerdObservationResponse row,
            BusinessHealthEvidenceBundle businessHealth,
            ExpectationValuationEvidenceBundle expectationValuation,
            Optional<MarketSectorEvidenceSnapshot> marketSector,
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
        addOptional(facts, "OBS.SECTOR_REFERENCE", DecisionArea.CHART_CROWD, "State 계산 참조 섹터 ETF",
                row.sectorEtf(), asOf, observedAt, row.stateModelVersion(), stateQuality);

        facts.addAll(businessHealth.facts());
        facts.addAll(expectationValuation.facts());
        if (marketSector.filter(MarketSectorEvidenceSnapshot::hasMarketContext).isPresent()) {
            addMarketSectorFacts(facts, marketSector.orElseThrow());
        } else {
            noView(facts, "MARKET.CONTEXT", DecisionArea.MARKET_SECTOR,
                    "시장·섹터 가격 맥락", asOf, generatedAt,
                    "관찰일 이전의 SPY 일봉이 200세션보다 부족합니다.");
        }
        noView(facts, "INFO.CHANGE", DecisionArea.INFORMATION_CHANGE,
                "확인된 정보 변화", asOf, generatedAt,
                "운영 방향 권한을 가진 비가격 정보가 없습니다.");
        return List.copyOf(facts);
    }

    private List<DecisionAreaAssessment> assessments(
            HerdObservationResponse row,
            DecisionAreaAssessment businessAssessment,
            DecisionAreaAssessment expectationAssessment,
            Optional<MarketSectorEvidenceSnapshot> marketSector,
            List<EvidenceFact> facts,
            EvidenceGateResult gate
    ) {
        List<String> chartIds = ids(facts, DecisionArea.CHART_CROWD, EvidenceQuality.AVAILABLE);
        List<String> marketIds = ids(facts, DecisionArea.MARKET_SECTOR, EvidenceQuality.AVAILABLE);
        return List.of(
                businessAssessment,
                expectationAssessment,
                new DecisionAreaAssessment(
                        DecisionArea.MARKET_SECTOR,
                        marketIds.isEmpty() ? AssessmentStatus.NO_VIEW : AssessmentStatus.PARTIAL,
                        marketHeadline(marketSector),
                        marketIds,
                        List.of(
                                "원시 일봉의 동시점 귀속이며 미래 방향 예측이 아닙니다.",
                                "HERD State나 행동 방향에 다시 가중하지 않습니다.")),
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

    private String marketHeadline(Optional<MarketSectorEvidenceSnapshot> snapshot) {
        if (snapshot.isEmpty() || !snapshot.orElseThrow().hasMarketContext()) {
            return "시장·섹터 가격 맥락 없음";
        }
        MarketSectorEvidenceSnapshot row = snapshot.orElseThrow();
        if (row.hasStockAttribution()) {
            return switch (row.downsideAttribution()) {
                case "MARKET_COMMON" -> "최근 약세의 시장 공통 기여가 가장 큼";
                case "SECTOR_COMMON" -> "최근 약세의 섹터 공통 기여가 가장 큼";
                case "STOCK_SPECIFIC" -> "최근 약세의 종목 고유 기여가 가장 큼";
                case "NO_DOWNSIDE_ATTRIBUTION" -> "최근 21세션 하락 경로 아님";
                default -> "최근 약세 기여 혼합";
            };
        }
        return row.hasSectorContext() ? "시장·섹터 가격 맥락 확인" : "시장 가격 맥락만 확인";
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

    private void addMarketSectorFacts(
            List<EvidenceFact> facts,
            MarketSectorEvidenceSnapshot row
    ) {
        addMarketSectorFact(facts, "MARKET.SPY.RETURN_63", "SPY 63세션 수익률",
                row.marketReturn63(), row);
        addMarketSectorFact(facts, "MARKET.SPY.DRAWDOWN_63", "SPY 63세션 고점 대비",
                row.marketDrawdown63(), row);
        addMarketSectorFact(facts, "MARKET.SPY.REALIZED_VOL_63", "SPY 63세션 실현 변동성",
                row.marketRealizedVolatility63(), row);
        addMarketSectorFact(facts, "MARKET.SPY.TREND_VS_SMA200", "SPY 200일 평균 대비",
                row.marketTrendVsSma200(), row);
        addMarketSectorFact(facts, "MARKET.SECTOR.RETURN_63", "섹터 ETF 63세션 수익률",
                row.sectorReturn63(), row);
        addMarketSectorFact(facts, "MARKET.SECTOR.RELATIVE_63", "섹터 ETF 대 SPY 63세션 상대수익",
                row.sectorRelativeReturn63(), row);
        addMarketSectorFact(facts, "MARKET.SECTOR.TREND_VS_SMA200", "섹터 ETF 200일 평균 대비",
                row.sectorTrendVsSma200(), row);
        addMarketSectorFact(facts, "MARKET.ATTRIBUTION.STOCK_RETURN_21", "종목 21세션 수익률",
                row.stockReturn21(), row);
        addMarketSectorFact(facts, "MARKET.ATTRIBUTION.MARKET_21", "시장 공통 기여 21세션",
                row.marketContribution21(), row);
        addMarketSectorFact(facts, "MARKET.ATTRIBUTION.SECTOR_21", "섹터 공통 기여 21세션",
                row.sectorContribution21(), row);
        addMarketSectorFact(facts, "MARKET.ATTRIBUTION.STOCK_SPECIFIC_21", "종목 고유 기여 21세션",
                row.stockSpecificContribution21(), row);
        addMarketSectorFact(facts, "MARKET.ATTRIBUTION.CLASS", "최근 약세 귀속",
                row.downsideAttribution(), row);
    }

    private void addMarketSectorFact(
            List<EvidenceFact> facts,
            String id,
            String label,
            Object value,
            MarketSectorEvidenceSnapshot row
    ) {
        facts.add(new EvidenceFact(
                id,
                DecisionArea.MARKET_SECTOR,
                label,
                value == null ? null : value.toString(),
                row.asOfDate(),
                row.observedAt(),
                "DAILY_PRICE_MARKET_SECTOR_CONTEXT",
                row.sourceVersion(),
                ASSET_TYPE,
                value == null ? EvidenceQuality.NO_VIEW : EvidenceQuality.AVAILABLE,
                false,
                true,
                true,
                STATE_MAXIMUM_AGE_DAYS));
    }

    private String defaultVersion(String version) {
        return version == null || version.isBlank() ? "UNKNOWN" : version;
    }
}
