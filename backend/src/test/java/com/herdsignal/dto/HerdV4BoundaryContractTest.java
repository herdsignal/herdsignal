package com.herdsignal.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.service.HerdScoreResponseMapper;
import com.herdsignal.service.HerdQualityEvaluator;
import com.herdsignal.service.UserActionBoundary;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.math.BigDecimal;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

class HerdV4BoundaryContractTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void preservesPythonGoldenValuesAtTheApiBoundary() throws Exception {
        try (InputStream stream = getClass().getResourceAsStream("/herd_v4_golden_cases.json")) {
            assertThat(stream).isNotNull();
            JsonNode contract = objectMapper.readTree(stream);

            for (JsonNode testCase : contract.path("cases")) {
                BigDecimal expectedBase = testCase.path("expectedBase").decimalValue();
                BigDecimal expectedV4 = testCase.path("expectedV4").decimalValue();
                HerdScore score = HerdScore.builder()
                        .ticker("TEST")
                        .scoreDate(LocalDate.of(2026, 1, 2))
                        .herdScore(expectedV4)
                        .herdStage(testCase.path("expectedStage").asText())
                        .signal("BUY")
                        .build();
                HerdIndicator indicator = HerdIndicator.builder()
                        .herdBase(expectedBase)
                        .epsMultiplier(testCase.path("epsMultiplier").decimalValue())
                        .sectorMultiplier(testCase.path("sectorMultiplier").decimalValue())
                        .build();

                HerdQualityEvaluator.HerdQuality quality =
                        new HerdQualityEvaluator().evaluate(score, indicator);
                HerdScoreResponse response = new HerdScoreResponseMapper(
                        new UserActionBoundary()
                ).map(
                        score, indicator, quality, null, null, null
                );

                assertThat(response.getOperationalModelVersion()).isEqualTo("HERD_v4");
                assertThat(response.getHerdBase()).isEqualByComparingTo(expectedBase);
                assertThat(response.getHerdV4()).isEqualByComparingTo(expectedV4);
                assertThat(response.getHerdScore()).isEqualByComparingTo(expectedV4);
                assertThat(response.getHerdStage()).isEqualTo(testCase.path("expectedStage").asText());
                assertThat(response.getSignal()).isEqualTo("HOLD");
                assertThat(response.getOperationalAction()).isEqualTo("HOLD");
                assertThat(response.getActionAuthorized()).isFalse();
                assertThat(response.getLegacySignal()).isEqualTo("BUY");
            }
        }
    }

    @Test
    void neverExposesLegacyResearchRatiosAsUserActions() {
        HerdScore score = HerdScore.builder()
                .ticker("NVDA")
                .scoreDate(LocalDate.of(2026, 7, 25))
                .herdScore(new BigDecimal("82"))
                .herdStage("Rush")
                .signal("SELL")
                .build();
        ActionDecision researchDecision = ActionDecision.builder()
                .actionModelVersion("HERD_v6.1")
                .actionModelStatus("RESEARCH_VALIDATION")
                .actionLabel("일부 익절")
                .actionGrade("ACTION")
                .actionRatio(new BigDecimal("0.15"))
                .researchActionRatio(new BigDecimal("0.15"))
                .researchActionLabel("일부 익절")
                .build();

        HerdScoreResponse response = new HerdScoreResponseMapper(
                new UserActionBoundary()
        ).map(score, null, null, researchDecision, null, null);

        assertThat(response.getSignal()).isEqualTo("HOLD");
        assertThat(response.getOperationalAction()).isEqualTo("HOLD");
        assertThat(response.getActionAuthorized()).isFalse();
        assertThat(response.getActionRatio()).isZero();
        assertThat(response.getActionGrade()).isEqualTo("NO_ACTION");
        assertThat(response.getActionLabel()).isEqualTo("상태 관찰");
        assertThat(response.getResearchActionRatio()).isNull();
        assertThat(response.getResearchActionLabel()).isNull();
        assertThat(response.getActionRegime()).isNull();
        assertThat(response.getLegacySignal()).isEqualTo("SELL");
    }
}
