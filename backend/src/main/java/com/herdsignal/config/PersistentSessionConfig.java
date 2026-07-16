package com.herdsignal.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.session.web.http.CookieSerializer;
import org.springframework.session.web.http.DefaultCookieSerializer;

import java.time.Duration;

/**
 * Google OAuth 로그인 세션을 브라우저와 서버 재시작 사이에도 유지한다.
 *
 * 세션 본문은 Spring Session JDBC가 MariaDB에 저장하고, 브라우저에는
 * 식별자만 HttpOnly 쿠키로 남긴다. 서버 세션의 미사용 만료 시간과
 * 브라우저 쿠키의 절대 보관 기간은 별도로 제한한다.
 */
@Configuration
@ConditionalOnProperty(name = "herdsignal.auth.enabled", havingValue = "true")
public class PersistentSessionConfig {

    @Bean
    CookieSerializer cookieSerializer(
            @Value("${herdsignal.auth.session-cookie-max-age:180d}") Duration cookieMaxAge,
            @Value("${herdsignal.auth.session-cookie-secure:false}") boolean secureCookie
    ) {
        long maxAgeSeconds = cookieMaxAge.toSeconds();
        if (maxAgeSeconds <= 0 || maxAgeSeconds > Integer.MAX_VALUE) {
            throw new IllegalArgumentException("세션 쿠키 보관 기간이 유효하지 않습니다.");
        }

        DefaultCookieSerializer serializer = new DefaultCookieSerializer();
        serializer.setCookieName("HERDSIGNAL_SESSION");
        serializer.setCookiePath("/");
        serializer.setCookieMaxAge((int) maxAgeSeconds);
        serializer.setUseHttpOnlyCookie(true);
        serializer.setUseSecureCookie(secureCookie);
        serializer.setSameSite("Lax");
        return serializer;
    }
}
