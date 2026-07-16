package com.herdsignal.config;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.session.web.http.CookieSerializer;
import org.springframework.session.web.http.DefaultCookieSerializer;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PersistentSessionConfigTest {

    private final PersistentSessionConfig config = new PersistentSessionConfig();

    @Test
    void createsPersistentCookieSerializer() {
        DefaultCookieSerializer serializer = (DefaultCookieSerializer) config.cookieSerializer(
                Duration.ofDays(180), false
        );
        MockHttpServletResponse response = new MockHttpServletResponse();
        serializer.writeCookieValue(new CookieSerializer.CookieValue(
                new MockHttpServletRequest(), response, "session-id"
        ));

        assertThat(response.getHeader("Set-Cookie"))
                .contains("HERDSIGNAL_SESSION=")
                .contains("Max-Age=15552000")
                .contains("HttpOnly")
                .contains("SameSite=Lax")
                .doesNotContain("Secure");
    }

    @Test
    void rejectsInvalidCookieDuration() {
        assertThatThrownBy(() -> config.cookieSerializer(Duration.ZERO, false))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
