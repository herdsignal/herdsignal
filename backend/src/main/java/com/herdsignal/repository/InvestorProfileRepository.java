package com.herdsignal.repository;

import com.herdsignal.domain.InvestorProfile;
import org.springframework.data.jpa.repository.JpaRepository;

public interface InvestorProfileRepository extends JpaRepository<InvestorProfile, String> {
}
