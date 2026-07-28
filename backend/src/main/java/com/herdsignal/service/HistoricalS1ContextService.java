package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.HerdObservation;
import com.herdsignal.dto.HistoricalS1ContextResponse;
import com.herdsignal.dto.HistoricalS1ContextSummary;
import com.herdsignal.repository.HerdObservationRepository;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 고정된 과거 S1 단계 진입 경로를 설명 통계로만 제공한다.
 * 현재 구성 종목 기반 자료이므로 행동 권한이나 시장 일반화에 사용하지 않는다.
 */
@Service
public class HistoricalS1ContextService {
    static final String RESOURCE =
            "research/historical_s1_product_context_v1.json";
    private static final String VERSION =
            "HERD_HISTORICAL_S1_PRODUCT_CONTEXT_V1";
    private static final String STATE_MODEL_VERSION = "HERD_STATE_S1";
    private static final String TICKER_PATTERN = "^[A-Z][A-Z0-9.-]{0,9}$";

    private final HerdObservationRepository observationRepository;
    private final JsonNode context;

    public HistoricalS1ContextService(
            HerdObservationRepository observationRepository,
            ObjectMapper objectMapper
    ) {
        this.observationRepository = observationRepository;
        this.context = load(objectMapper);
        validateRoot(context);
    }

    @Transactional(readOnly = true)
    public HistoricalS1ContextResponse getCurrentStageContext(
            String rawTicker
    ) {
        String ticker = normalizeTicker(rawTicker);
        HerdObservation latest = observationRepository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        ticker,
                        STATE_MODEL_VERSION
                )
                .orElse(null);
        if (latest == null || latest.getHerdStage() == null) {
            return unavailable(ticker, null);
        }
        String stage = latest.getHerdStage();
        JsonNode tickerContext = context.path("tickers")
                .path(ticker)
                .path(stage);
        if (
                "DESCRIPTIVE_ONLY".equals(
                        tickerContext.path("evidenceStatus").asText()
                )
        ) {
            return response(
                    ticker,
                    stage,
                    "TICKER_HISTORY",
                    context.path("minimumTickerEpisodes").asInt(),
                    tickerContext
            );
        }
        JsonNode referenceContext = context.path("reference").path(stage);
        if (
                "DESCRIPTIVE_ONLY".equals(
                        referenceContext.path("evidenceStatus").asText()
                )
        ) {
            return response(
                    ticker,
                    stage,
                    "CURRENT_CONSTITUENT_REFERENCE",
                    context.path("minimumReferenceEpisodes").asInt(),
                    referenceContext
            );
        }
        return unavailable(ticker, stage);
    }

    private HistoricalS1ContextResponse response(
            String ticker,
            String stage,
            String scope,
            int minimumEpisodes,
            JsonNode selected
    ) {
        List<HistoricalS1ContextSummary> summaries = new ArrayList<>();
        selected.path("summaries").forEach(item ->
                summaries.add(new HistoricalS1ContextSummary(
                        item.path("horizonSessions").asInt(),
                        item.path("completedEpisodes").asInt(),
                        decimal(item, "medianReturnPct"),
                        decimal(item, "positiveRatePct"),
                        decimal(item, "medianMfePct"),
                        decimal(item, "medianMaePct")
                ))
        );
        return new HistoricalS1ContextResponse(
                "AVAILABLE",
                "DESCRIPTIVE_ONLY",
                scope,
                ticker,
                stage,
                context.path("stateModelVersion").asText(),
                LocalDate.parse(context.path("historyStartDate").asText()),
                LocalDate.parse(context.path("historyEndDate").asText()),
                false,
                minimumEpisodes,
                selected.path("episodeCount").asInt(),
                List.copyOf(summaries),
                false,
                "HOLD",
                0.0
        );
    }

    private HistoricalS1ContextResponse unavailable(
            String ticker,
            String stage
    ) {
        return new HistoricalS1ContextResponse(
                "UNAVAILABLE",
                "INSUFFICIENT_SAMPLE",
                null,
                ticker,
                stage,
                STATE_MODEL_VERSION,
                LocalDate.parse(context.path("historyStartDate").asText()),
                LocalDate.parse(context.path("historyEndDate").asText()),
                false,
                context.path("minimumReferenceEpisodes").asInt(),
                0,
                List.of(),
                false,
                "HOLD",
                0.0
        );
    }

    private JsonNode load(ObjectMapper objectMapper) {
        try {
            return objectMapper.readTree(
                    new ClassPathResource(RESOURCE).getInputStream()
            );
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "과거 S1 설명 자료를 읽을 수 없습니다.",
                    exception
            );
        }
    }

    private void validateRoot(JsonNode root) {
        if (
                !VERSION.equals(root.path("schemaVersion").asText())
                || !STATE_MODEL_VERSION.equals(
                        root.path("stateModelVersion").asText()
                )
                || root.path("survivorshipSafe").asBoolean(true)
                || root.path("directionPrediction").asBoolean(true)
                || !"HOLD".equals(root.path("operationalAction").asText())
                || root.path("operationalActionRatio").asDouble(-1) != 0.0
        ) {
            throw new IllegalStateException(
                    "과거 S1 설명 자료의 행동 차단 계약이 유효하지 않습니다."
            );
        }
    }

    private BigDecimal decimal(JsonNode node, String field) {
        return node.path(field).decimalValue();
    }

    private String normalizeTicker(String rawTicker) {
        if (rawTicker == null || rawTicker.isBlank()) {
            throw new IllegalArgumentException("티커를 입력해주세요.");
        }
        String ticker = rawTicker.trim().toUpperCase(Locale.ROOT);
        if (!ticker.matches(TICKER_PATTERN)) {
            throw new IllegalArgumentException(
                    "올바른 미국 주식 티커 형식이 아닙니다."
            );
        }
        return ticker;
    }
}
