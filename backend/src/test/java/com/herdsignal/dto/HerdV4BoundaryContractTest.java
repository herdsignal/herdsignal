package com.herdsignal.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
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
                        .signal("HOLD")
                        .build();
                HerdIndicator indicator = HerdIndicator.builder()
                        .herdBase(expectedBase)
                        .epsMultiplier(testCase.path("epsMultiplier").decimalValue())
                        .sectorMultiplier(testCase.path("sectorMultiplier").decimalValue())
                        .build();

                HerdScoreResponse response = HerdScoreResponse.of(
                        score, indicator, null, null, null, null,
                        null, null, null, null
                );

                assertThat(response.getOperationalModelVersion()).isEqualTo("HERD_v4");
                assertThat(response.getHerdBase()).isEqualByComparingTo(expectedBase);
                assertThat(response.getHerdV4()).isEqualByComparingTo(expectedV4);
                assertThat(response.getHerdScore()).isEqualByComparingTo(expectedV4);
                assertThat(response.getHerdStage()).isEqualTo(testCase.path("expectedStage").asText());
            }
        }
    }
}
