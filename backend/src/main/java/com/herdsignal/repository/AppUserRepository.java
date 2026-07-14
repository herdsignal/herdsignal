package com.herdsignal.repository;

import com.herdsignal.domain.AppUser;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AppUserRepository extends JpaRepository<AppUser, String> {
    Optional<AppUser> findByProviderAndProviderSubject(String provider, String providerSubject);
}
