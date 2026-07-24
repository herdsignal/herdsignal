package com.herdsignal.service;

import com.herdsignal.domain.SignalJournal;
import com.herdsignal.dto.SignalJournalRequest;
import com.herdsignal.dto.SignalJournalResponse;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.SignalJournalRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * HERD 판단 기록 관리 서비스.
 * 호출자가 전달한 인증 사용자 ID 단위로 판단 기록을 격리한다.
 */
@Service
@RequiredArgsConstructor
public class SignalJournalService {

    private final SignalJournalRepository signalJournalRepository;
    private final DailyPriceRepository dailyPriceRepository;
    private final UserActionBoundary actionBoundary;

    @Transactional(readOnly = true)
    public List<SignalJournalResponse> getJournals(String userId, String ticker) {
        String normalizedTicker = normalizeTickerOrNull(ticker);
        List<SignalJournal> rows = normalizedTicker == null
                ? signalJournalRepository.findByUserIdOrderByRecordedAtDesc(userId)
                : signalJournalRepository.findByUserIdAndTickerOrderByRecordedAtDesc(userId, normalizedTicker);

        return rows.stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public SignalJournalResponse createJournal(String userId, SignalJournalRequest request) {
        String ticker = normalizeTicker(request.getTicker());
        String actionType = normalizeActionType(request.getActionType());
        UserActionBoundary.Output modelAction = actionBoundary.locked();
        LocalDateTime now = LocalDateTime.now();

        SignalJournal journal = SignalJournal.builder()
                .userId(userId)
                .ticker(ticker)
                .actionType(actionType)
                .actionLabel(cleanText(request.getActionLabel(), 50))
                .scoreDate(request.getScoreDate())
                .herdScore(request.getHerdScore())
                .herdStage(cleanText(request.getHerdStage(), 20))
                .signal(modelAction.action())
                .signalLabel("State S1 관찰")
                .actionRatio(modelAction.ratio())
                .signalDurationDays(null)
                .stageDurationDays(request.getStageDurationDays())
                .price(request.getPrice())
                .quantity(request.getQuantity())
                .amount(request.getAmount())
                .profitPct(request.getProfitPct())
                .memo(cleanText(request.getMemo(), 1000))
                .recordedAt(request.getRecordedAt() != null ? request.getRecordedAt() : now)
                .createdAt(now)
                .updatedAt(now)
                .build();

        SignalJournal saved = signalJournalRepository.save(journal);
        return toResponse(saved);
    }

    @Transactional
    public void deleteJournal(String userId, Long id) {
        SignalJournal journal = signalJournalRepository.findByIdAndUserId(id, userId)
                .orElseThrow(() -> new ResourceNotFoundException("판단 기록을 찾을 수 없습니다."));
        signalJournalRepository.delete(journal);
    }

    private String normalizeTicker(String ticker) {
        if (ticker == null || ticker.isBlank()) {
            throw new IllegalArgumentException("티커는 필수입니다.");
        }
        String normalized = ticker.trim().toUpperCase();
        if (!normalized.matches("^[A-Z0-9.\\-]{1,10}$")) {
            throw new IllegalArgumentException("티커 형식이 올바르지 않습니다.");
        }
        return normalized;
    }

    private String normalizeTickerOrNull(String ticker) {
        if (ticker == null || ticker.isBlank()) return null;
        return normalizeTicker(ticker);
    }

    private String normalizeActionType(String actionType) {
        if (actionType == null || actionType.isBlank()) {
            throw new IllegalArgumentException("판단 유형은 필수입니다.");
        }
        String normalized = actionType.trim().toUpperCase();
        if (!List.of("BUY", "HOLD", "SELL").contains(normalized)) {
            throw new IllegalArgumentException("판단 유형은 BUY/HOLD/SELL 중 하나여야 합니다.");
        }
        return normalized;
    }

    private String cleanText(String value, int maxLength) {
        if (value == null) return null;
        String trimmed = value.trim();
        if (trimmed.isEmpty()) return null;
        if (trimmed.length() > maxLength) {
            throw new IllegalArgumentException("텍스트는 " + maxLength + "자 이하여야 합니다.");
        }
        return trimmed;
    }

    private BigDecimal latestClose(String ticker) {
        if (ticker == null || ticker.isBlank()) return null;
        return dailyPriceRepository.findTop2ByTickerOrderByPriceDateDesc(ticker).stream()
                .filter((price) -> price.getClosePrice() != null)
                .findFirst()
                .map((price) -> price.getClosePrice())
                .orElse(null);
    }

    private SignalJournalResponse toResponse(SignalJournal journal) {
        UserActionBoundary.Output modelAction = actionBoundary.locked();
        return SignalJournalResponse.from(
                journal,
                latestClose(journal.getTicker()),
                modelAction.action(),
                modelAction.ratio()
        );
    }
}
