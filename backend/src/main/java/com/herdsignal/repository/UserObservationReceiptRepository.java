package com.herdsignal.repository;

import com.herdsignal.domain.UserObservationReceipt;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface UserObservationReceiptRepository
        extends JpaRepository<UserObservationReceipt, Long> {
    List<UserObservationReceipt> findByUserId(String userId);

    Optional<UserObservationReceipt> findByUserIdAndTicker(
            String userId,
            String ticker
    );
}
