package com.herdsignal.service;

import com.herdsignal.domain.AppUser;
import com.herdsignal.dto.AuthUserResponse;
import com.herdsignal.repository.AppUserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class CurrentUserService {
    private final AppUserRepository repository;

    @Value("${herdsignal.auth.enabled:false}")
    private boolean authEnabled;

    public String requireUserId() {
        if (!authEnabled) return "local";
        return requireUser().getId();
    }

    public String userIdOrNull() {
        if (!authEnabled) return "local";
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (!isOidcAuthentication(authentication)) {
            return null;
        }
        OidcUser oidcUser = (OidcUser) authentication.getPrincipal();
        return findGoogleUser(oidcUser.getSubject()).getId();
    }

    public AuthUserResponse currentUser() {
        if (!authEnabled) return AuthUserResponse.local();
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (!isOidcAuthentication(authentication)) {
            return AuthUserResponse.anonymous();
        }
        OidcUser oidcUser = (OidcUser) authentication.getPrincipal();
        return AuthUserResponse.authenticated(findGoogleUser(oidcUser.getSubject()));
    }

    private AppUser requireUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (!isOidcAuthentication(authentication)) {
            throw new IllegalStateException("로그인이 필요합니다.");
        }
        OidcUser oidcUser = (OidcUser) authentication.getPrincipal();
        return findGoogleUser(oidcUser.getSubject());
    }

    private boolean isOidcAuthentication(Authentication authentication) {
        return authentication != null
                && authentication.isAuthenticated()
                && authentication.getPrincipal() instanceof OidcUser;
    }

    private AppUser findGoogleUser(String subject) {
        return repository.findByProviderAndProviderSubject("GOOGLE", subject)
                .orElseThrow(() -> new IllegalStateException("로그인 사용자 정보를 찾을 수 없습니다."));
    }
}
