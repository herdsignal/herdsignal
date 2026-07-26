package com.herdsignal.service;

import com.herdsignal.domain.AppUser;
import com.herdsignal.repository.AppUserRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.TestingAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class CurrentUserServiceTest {

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void localModeAllowsOwnerOperations() {
        CurrentUserService service = new CurrentUserService(mock(AppUserRepository.class));
        ReflectionTestUtils.setField(service, "authEnabled", false);

        assertThat(service.isOwner()).isTrue();
    }

    @Test
    void authenticatedModeFailsClosedWithoutOwnerEmail() {
        CurrentUserService service = new CurrentUserService(mock(AppUserRepository.class));
        ReflectionTestUtils.setField(service, "authEnabled", true);
        ReflectionTestUtils.setField(service, "ownerEmail", "");

        assertThat(service.isOwner()).isFalse();
    }

    @Test
    void onlyConfiguredOwnerAccountAllowsOperations() {
        AppUserRepository repository = mock(AppUserRepository.class);
        AppUser user = AppUser.builder()
                .id("owner-id")
                .provider("GOOGLE")
                .providerSubject("subject")
                .email("owner@example.com")
                .displayName("Owner")
                .role("USER")
                .build();
        when(repository.findByProviderAndProviderSubject("GOOGLE", "subject"))
                .thenReturn(Optional.of(user));
        OidcUser principal = mock(OidcUser.class);
        when(principal.getSubject()).thenReturn("subject");
        SecurityContextHolder.getContext().setAuthentication(
                new TestingAuthenticationToken(principal, null, "ROLE_USER")
        );
        CurrentUserService service = new CurrentUserService(repository);
        ReflectionTestUtils.setField(service, "authEnabled", true);
        ReflectionTestUtils.setField(service, "ownerEmail", "OWNER@example.com");

        assertThat(service.isOwner()).isTrue();
    }
}
