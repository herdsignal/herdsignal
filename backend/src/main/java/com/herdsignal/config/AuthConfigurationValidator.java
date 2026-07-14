package com.herdsignal.config;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.net.URI;

@Component
@ConditionalOnProperty(name = "herdsignal.auth.enabled", havingValue = "true")
public class AuthConfigurationValidator implements InitializingBean {
    private final String clientId;
    private final String clientSecret;
    private final String frontendUrl;

    public AuthConfigurationValidator(
            @Value("${spring.security.oauth2.client.registration.google.client-id:}") String clientId,
            @Value("${spring.security.oauth2.client.registration.google.client-secret:}") String clientSecret,
            @Value("${herdsignal.auth.frontend-url:http://localhost:5173}") String frontendUrl) {
        this.clientId = clientId;
        this.clientSecret = clientSecret;
        this.frontendUrl = frontendUrl;
    }

    @Override
    public void afterPropertiesSet() {
        requireConfigured(clientId, "GOOGLE_CLIENT_ID");
        requireConfigured(clientSecret, "GOOGLE_CLIENT_SECRET");
        validateFrontendUrl(frontendUrl);
    }

    private void requireConfigured(String value, String name) {
        if (value == null || value.isBlank() || "disabled".equalsIgnoreCase(value)) {
            throw new IllegalStateException("AUTH_ENABLED=true일 때 " + name + " 설정이 필요합니다.");
        }
    }

    private void validateFrontendUrl(String value) {
        try {
            URI uri = URI.create(value);
            if (!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme()))
                    || uri.getHost() == null || uri.getQuery() != null || uri.getFragment() != null) {
                throw new IllegalArgumentException();
            }
        } catch (IllegalArgumentException e) {
            throw new IllegalStateException("FRONTEND_URL은 유효한 http(s) 주소여야 합니다.");
        }
    }
}
