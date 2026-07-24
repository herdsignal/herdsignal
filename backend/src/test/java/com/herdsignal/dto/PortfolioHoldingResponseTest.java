package com.herdsignal.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.UserPortfolio;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class PortfolioHoldingResponseTest {

    @Test
    void doesNotExposePersistenceOrUserIdentityFields() {
        UserPortfolio entity = UserPortfolio.builder()
                .id(99L)
                .userId("secret-user-id")
                .ticker("NVDA")
                .avgPrice(new BigDecimal("100"))
                .quantity(new BigDecimal("2"))
                .build();

        JsonNode json = new ObjectMapper().valueToTree(PortfolioHoldingResponse.from(entity));

        assertThat(json.has("id")).isFalse();
        assertThat(json.has("userId")).isFalse();
        assertThat(json.get("ticker").asText()).isEqualTo("NVDA");
    }
}
