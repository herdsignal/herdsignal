package com.herdsignal.config;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AuthConfigurationValidatorTest {

    @Test
    void acceptsCompleteOAuthConfiguration() {
        var validator = new AuthConfigurationValidator(
                "client.apps.googleusercontent.com", "GOCSPX-secret", "http://localhost:5173");

        assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
    }

    @Test
    void rejectsMissingSecret() {
        var validator = new AuthConfigurationValidator(
                "client.apps.googleusercontent.com", "", "http://localhost:5173");

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("GOOGLE_CLIENT_SECRET");
    }

    @Test
    void rejectsMalformedFrontendUrl() {
        var validator = new AuthConfigurationValidator(
                "client.apps.googleusercontent.com", "GOCSPX-secret", "not-a-url");

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("FRONTEND_URL");
    }
}
