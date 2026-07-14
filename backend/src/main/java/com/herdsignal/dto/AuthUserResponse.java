package com.herdsignal.dto;

import com.herdsignal.domain.AppUser;

public record AuthUserResponse(
        boolean authenticated,
        String id,
        String email,
        String displayName,
        String profileImageUrl,
        boolean developmentMode
) {
    public static AuthUserResponse authenticated(AppUser user) {
        return new AuthUserResponse(true, user.getId(), user.getEmail(), user.getDisplayName(),
                user.getProfileImageUrl(), false);
    }

    public static AuthUserResponse local() {
        return new AuthUserResponse(true, "local", null, "Local user", null, true);
    }

    public static AuthUserResponse anonymous() {
        return new AuthUserResponse(false, null, null, null, null, false);
    }
}
