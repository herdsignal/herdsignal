package com.herdsignal.service.decision;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.OperatingReviewSnapshot;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.OperatingReviewSnapshotRepository;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.PricePathAttributionService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HexFormat;
import java.util.List;

/** 판단 원문을 해시와 함께 추가하고 이후 가격 경로를 귀속한다. */
@Service
public class OperatingReviewSnapshotService {
    private static final String DECISION_MODEL_VERSION = "LONG_TERM_OPERATING_V1";
    private static final List<Integer> HORIZONS = List.of(1, 3, 6);

    private final LongTermOperatingReviewService reviewService;
    private final CurrentUserService currentUserService;
    private final OperatingReviewSnapshotRepository repository;
    private final DailyPriceRepository dailyPriceRepository;
    private final ObjectMapper objectMapper;
    private final PricePathAttributionService pricePathAttributionService;
    private final Clock clock;

    @Autowired
    public OperatingReviewSnapshotService(
            LongTermOperatingReviewService reviewService,
            CurrentUserService currentUserService,
            OperatingReviewSnapshotRepository repository,
            DailyPriceRepository dailyPriceRepository,
            ObjectMapper objectMapper,
            PricePathAttributionService pricePathAttributionService
    ) {
        this(reviewService, currentUserService, repository, dailyPriceRepository,
                objectMapper, pricePathAttributionService, Clock.systemUTC());
    }

    OperatingReviewSnapshotService(
            LongTermOperatingReviewService reviewService,
            CurrentUserService currentUserService,
            OperatingReviewSnapshotRepository repository,
            DailyPriceRepository dailyPriceRepository,
            ObjectMapper objectMapper,
            Clock clock
    ) {
        this(reviewService, currentUserService, repository, dailyPriceRepository,
                objectMapper, new PricePathAttributionService(dailyPriceRepository), clock);
    }

    OperatingReviewSnapshotService(
            LongTermOperatingReviewService reviewService,
            CurrentUserService currentUserService,
            OperatingReviewSnapshotRepository repository,
            DailyPriceRepository dailyPriceRepository,
            ObjectMapper objectMapper,
            PricePathAttributionService pricePathAttributionService,
            Clock clock
    ) {
        this.reviewService = reviewService;
        this.currentUserService = currentUserService;
        this.repository = repository;
        this.dailyPriceRepository = dailyPriceRepository;
        this.objectMapper = objectMapper;
        this.pricePathAttributionService = pricePathAttributionService;
        this.clock = clock;
    }

    @Transactional
    public OperatingReviewSnapshotResponse record(String ticker) {
        PersonalOperatingReviewResponse review = reviewService.review(ticker);
        String payload = serialize(review);
        DailyPrice reference = dailyPriceRepository
                .findTopByTickerAndClosePriceIsNotNullOrderByPriceDateDesc(review.ticker())
                .orElse(null);
        OperatingReviewSnapshot saved = repository.save(OperatingReviewSnapshot.builder()
                .userId(currentUserService.requireUserId())
                .ticker(review.ticker())
                .reviewedAt(LocalDateTime.now(clock))
                .observationDate(observationDate(review.objective().evidencePacket()))
                .referencePriceDate(reference == null ? null : reference.getPriceDate())
                .referencePrice(reference == null ? null : reference.getClosePrice())
                .decisionCode(review.synthesis().decision().name())
                .actionAuthorized(review.synthesis().actionAuthorized())
                .actionRatio(BigDecimal.valueOf(review.synthesis().operationalActionRatio()))
                .evidenceSchemaVersion(review.objective().evidencePacket() == null
                        ? "UNAVAILABLE" : review.objective().evidencePacket().schemaVersion())
                .decisionModelVersion(DECISION_MODEL_VERSION)
                .payloadJson(payload)
                .payloadSha256(sha256(payload))
                .build());
        return response(saved);
    }

    @Transactional(readOnly = true)
    public List<OperatingReviewSnapshotResponse> history(String ticker) {
        String normalized = ticker == null ? "" : ticker.trim().toUpperCase();
        return repository.findByUserIdAndTickerOrderByReviewedAtDesc(
                        currentUserService.requireUserId(), normalized).stream()
                .map(this::response)
                .toList();
    }

    private OperatingReviewSnapshotResponse response(OperatingReviewSnapshot row) {
        return new OperatingReviewSnapshotResponse(
                row.getId(), row.getTicker(), row.getReviewedAt(), row.getObservationDate(),
                row.getReferencePriceDate(), row.getReferencePrice(), row.getDecisionCode(),
                row.isActionAuthorized(), row.getActionRatio(), row.getEvidenceSchemaVersion(),
                row.getDecisionModelVersion(), row.getPayloadSha256(), outcomes(row));
    }

    private LocalDate observationDate(EvidencePacket packet) {
        if (packet == null) {
            return null;
        }
        return packet.facts().stream()
                .filter(fact -> "OBS.STATE_SCORE".equals(fact.id()))
                .map(EvidenceFact::asOfDate)
                .findFirst()
                .orElse(packet.generatedAt() == null ? null : packet.generatedAt().toLocalDate());
    }

    private List<OperatingReviewOutcome> outcomes(OperatingReviewSnapshot row) {
        LocalDate latestMarketDate = dailyPriceRepository.findLatestPriceDate().orElse(null);
        return pricePathAttributionService.evaluate(
                        row.getTicker(), row.getReferencePriceDate(), row.getReferencePrice(),
                        HORIZONS, latestMarketDate).stream()
                .map(this::outcome)
                .toList();
    }

    private OperatingReviewOutcome outcome(PricePathAttributionService.Outcome row) {
        return new OperatingReviewOutcome(
                row.horizonMonths(), row.targetDate(), row.status(), row.priceDate(),
                row.closePrice(), row.returnPct(), null);
    }

    private String serialize(PersonalOperatingReviewResponse review) {
        try {
            return objectMapper.writeValueAsString(review);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("운용 판단 스냅샷을 직렬화할 수 없습니다.", exception);
        }
    }

    private String sha256(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", exception);
        }
    }
}
