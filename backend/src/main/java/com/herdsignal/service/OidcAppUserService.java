package com.herdsignal.service;

import com.herdsignal.domain.AppUser;
import com.herdsignal.repository.AppUserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserRequest;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserService;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class OidcAppUserService extends OidcUserService {
    private final AppUserRepository repository;
    private final LocalUserDataClaimService localUserDataClaimService;

    @Override
    @Transactional
    public OidcUser loadUser(OidcUserRequest request) throws OAuth2AuthenticationException {
        OidcUser oidcUser = super.loadUser(request);
        String subject = oidcUser.getSubject();
        String email = oidcUser.getEmail();
        if (email == null || email.isBlank()) {
            throw new OAuth2AuthenticationException("Google 계정 이메일을 확인할 수 없습니다.");
        }

        LocalDateTime now = LocalDateTime.now();
        AppUser user = repository.findByProviderAndProviderSubject("GOOGLE", subject)
                .orElseGet(() -> AppUser.builder()
                        .id(UUID.randomUUID().toString())
                        .provider("GOOGLE")
                        .providerSubject(subject)
                        .email(email)
                        .displayName(displayName(oidcUser, email))
                        .profileImageUrl(oidcUser.getPicture())
                        .role("USER")
                        .createdAt(now)
                        .lastLoginAt(now)
                        .build());
        user.updateProfile(email, displayName(oidcUser, email), oidcUser.getPicture(), now);
        repository.save(user);
        localUserDataClaimService.claimIfOwner(email, user.getId());
        return oidcUser;
    }

    private String displayName(OidcUser user, String email) {
        String name = user.getFullName();
        return name == null || name.isBlank() ? email : name;
    }
}
