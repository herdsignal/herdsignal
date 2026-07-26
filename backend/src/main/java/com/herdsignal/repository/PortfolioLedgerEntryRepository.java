package com.herdsignal.repository;

import com.herdsignal.domain.PortfolioLedgerEntry;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PortfolioLedgerEntryRepository
        extends JpaRepository<PortfolioLedgerEntry, Long> {

    List<PortfolioLedgerEntry> findByUserIdOrderByOccurredOnDescIdDesc(String userId);

    List<PortfolioLedgerEntry> findByUserIdOrderByOccurredOnAscIdAsc(String userId);

    List<PortfolioLedgerEntry> findByUserIdAndTickerOrderByOccurredOnDescIdDesc(
            String userId,
            String ticker
    );

    Optional<PortfolioLedgerEntry> findByIdAndUserId(Long id, String userId);
}
