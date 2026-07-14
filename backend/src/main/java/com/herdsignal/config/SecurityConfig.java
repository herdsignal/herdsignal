package com.herdsignal.config;

import com.herdsignal.service.OidcAppUserService;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.web.csrf.CsrfTokenRequestAttributeHandler;

@Configuration
public class SecurityConfig {

    @Configuration
    @ConditionalOnProperty(name = "herdsignal.auth.enabled", havingValue = "true")
    @RequiredArgsConstructor
    static class OAuthSecurity {
        private final OidcAppUserService oidcAppUserService;

        @Value("${herdsignal.auth.frontend-url:http://localhost:5173}")
        private String frontendUrl;

        @Bean
        @Order(1)
        SecurityFilterChain oauthFilterChain(HttpSecurity http) throws Exception {
            CookieCsrfTokenRepository csrfRepository = CookieCsrfTokenRepository.withHttpOnlyFalse();
            CsrfTokenRequestAttributeHandler csrfHandler = new CsrfTokenRequestAttributeHandler();
            csrfHandler.setCsrfRequestAttributeName(null);

            http
                    .csrf(csrf -> csrf
                            .csrfTokenRepository(csrfRepository)
                            .csrfTokenRequestHandler(csrfHandler))
                    .sessionManagement(session -> session
                            .sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED)
                            .sessionFixation().migrateSession())
                    .authorizeHttpRequests(auth -> auth
                            .requestMatchers("/oauth2/**", "/login/**", "/error", "/actuator/health").permitAll()
                            .requestMatchers("/api/auth/**", "/api/model/**").permitAll()
                            .requestMatchers(HttpMethod.GET, "/api/stocks/**").permitAll()
                            .anyRequest().authenticated())
                    .oauth2Login(login -> login
                            .userInfoEndpoint(userInfo -> userInfo.oidcUserService(oidcAppUserService))
                            .successHandler((request, response, authentication) ->
                                    response.sendRedirect(frontendUrl + "/app"))
                            .failureHandler((request, response, exception) ->
                                    response.sendRedirect(frontendUrl + "/login?error=oauth")))
                    .logout(logout -> logout
                            .logoutUrl("/api/auth/logout")
                            .logoutSuccessHandler((request, response, authentication) ->
                                    response.setStatus(HttpServletResponse.SC_NO_CONTENT))
                            .invalidateHttpSession(true)
                            .clearAuthentication(true)
                            .deleteCookies("JSESSIONID"))
                    .exceptionHandling(exceptions -> exceptions
                            .authenticationEntryPoint((request, response, exception) ->
                                    response.sendError(HttpServletResponse.SC_UNAUTHORIZED)));
            return http.build();
        }
    }

    @Configuration
    @ConditionalOnProperty(name = "herdsignal.auth.enabled", havingValue = "false", matchIfMissing = true)
    static class LocalDevelopmentSecurity {
        @Bean
        @Order(2)
        SecurityFilterChain localFilterChain(HttpSecurity http) throws Exception {
            http
                    .csrf(csrf -> csrf.disable())
                    .authorizeHttpRequests(auth -> auth.anyRequest().permitAll());
            return http.build();
        }
    }
}
