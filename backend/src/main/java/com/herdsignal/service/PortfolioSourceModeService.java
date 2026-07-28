package com.herdsignal.service;

import com.herdsignal.exception.DuplicateResourceException;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class PortfolioSourceModeService {

    static final String OPENING_SNAPSHOT_SOURCE = "OPENING_SNAPSHOT";

    private final PortfolioLedgerEntryRepository ledgerRepository;

    @Transactional(readOnly = true)
    public boolean isLedgerManaged(String userId) {
        return ledgerRepository.existsByUserIdAndSource(
                userId,
                OPENING_SNAPSHOT_SOURCE
        );
    }

    public void requireManualWriteAllowed(String userId) {
        if (isLedgerManaged(userId)) {
            throw new DuplicateResourceException(
                    "이 계좌는 거래 원장을 기준으로 관리됩니다. 원장에 거래를 기록해주세요."
            );
        }
    }
}
