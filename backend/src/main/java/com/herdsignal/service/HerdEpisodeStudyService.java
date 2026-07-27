package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.HerdObservation;
import com.herdsignal.dto.HerdEpisodeHorizonOutcome;
import com.herdsignal.dto.HerdEpisodeHorizonSummary;
import com.herdsignal.dto.HerdEpisodeOutcome;
import com.herdsignal.dto.HerdEpisodeStudyResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.HerdObservationRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/**
 * 같은 HERD 단계에 새로 진입한 사건 이후의 가격 경로를 기술 통계로만 계산한다.
 * 매주를 독립 사건으로 중복 집계하지 않고 첫 관찰은 좌측 절단 표본이라 제외한다.
 */
@Service
public class HerdEpisodeStudyService {
    static final String STATE_MODEL_VERSION = "HERD_STATE_S1";
    static final int OBSERVATION_LIMIT = 260;
    static final int MINIMUM_COMPLETED_EPISODES = 5;
    private static final int[] HORIZON_WEEKS = {1, 4, 12};
    private static final String TICKER_PATTERN = "^[A-Z][A-Z0-9.-]{0,9}$";

    private final HerdObservationRepository observationRepository;
    private final DailyPriceRepository priceRepository;

    public HerdEpisodeStudyService(
            HerdObservationRepository observationRepository,
            DailyPriceRepository priceRepository
    ) {
        this.observationRepository = observationRepository;
        this.priceRepository = priceRepository;
    }

    @Transactional(readOnly = true)
    public HerdEpisodeStudyResponse studyCurrentStage(String rawTicker) {
        String ticker = normalizeTicker(rawTicker);
        List<HerdObservation> observations = observationRepository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        ticker,
                        STATE_MODEL_VERSION,
                        PageRequest.of(0, OBSERVATION_LIMIT)
                )
                .stream()
                .sorted(Comparator.comparing(HerdObservation::getObservationDate))
                .toList();
        if (observations.isEmpty()) {
            return unavailable(ticker);
        }

        String currentStage = observations.get(observations.size() - 1)
                .getHerdStage();
        List<HerdObservation> entries = stageEntries(observations, currentStage);
        if (entries.isEmpty()) {
            return response(ticker, currentStage, List.of());
        }

        LocalDate firstEntry = entries.get(0).getLastObservedSession();
        LocalDate latestPriceDate = priceRepository
                .findTopByTickerAndClosePriceIsNotNullOrderByPriceDateDesc(ticker)
                .map(DailyPrice::getPriceDate)
                .orElse(firstEntry);
        List<DailyPrice> prices = priceRepository.findPricesForTickerBetween(
                ticker,
                firstEntry,
                latestPriceDate
        );
        List<HerdEpisodeOutcome> episodes = entries.stream()
                .map(entry -> buildEpisode(entry, prices))
                .filter(episode -> episode.entryPrice() != null)
                .toList();
        return response(ticker, currentStage, episodes);
    }

    private List<HerdObservation> stageEntries(
            List<HerdObservation> observations,
            String targetStage
    ) {
        List<HerdObservation> entries = new ArrayList<>();
        for (int index = 1; index < observations.size(); index++) {
            HerdObservation current = observations.get(index);
            HerdObservation previous = observations.get(index - 1);
            if (targetStage.equals(current.getHerdStage())
                    && !targetStage.equals(previous.getHerdStage())) {
                entries.add(current);
            }
        }
        return entries;
    }

    private HerdEpisodeOutcome buildEpisode(
            HerdObservation entry,
            List<DailyPrice> prices
    ) {
        DailyPrice entryPrice = prices.stream()
                .filter(price -> price.getPriceDate().equals(
                        entry.getLastObservedSession()
                ))
                .findFirst()
                .orElse(null);
        if (entryPrice == null) {
            return new HerdEpisodeOutcome(
                    entry.getObservationDate(),
                    entry.getLastObservedSession(),
                    entry.getHerdStage(),
                    entry.getStateScore(),
                    null,
                    List.of()
            );
        }
        List<HerdEpisodeHorizonOutcome> outcomes = new ArrayList<>();
        for (int weeks : HORIZON_WEEKS) {
            outcomes.add(horizonOutcome(entryPrice, prices, weeks));
        }
        return new HerdEpisodeOutcome(
                entry.getObservationDate(),
                entry.getLastObservedSession(),
                entry.getHerdStage(),
                entry.getStateScore(),
                entryPrice.getClosePrice(),
                outcomes
        );
    }

    private HerdEpisodeHorizonOutcome horizonOutcome(
            DailyPrice entry,
            List<DailyPrice> prices,
            int weeks
    ) {
        LocalDate target = entry.getPriceDate().plusWeeks(weeks);
        DailyPrice end = prices.stream()
                .filter(price -> !price.getPriceDate().isBefore(target))
                .filter(price -> !price.getPriceDate().isAfter(
                        target.plusDays(7)
                ))
                .findFirst()
                .orElse(null);
        if (end == null) {
            return new HerdEpisodeHorizonOutcome(
                    weeks, "PENDING", null, null, null
            );
        }
        BigDecimal entryValue = entry.getClosePrice();
        BigDecimal returnPct = percentChange(
                end.getClosePrice(),
                entryValue
        );
        BigDecimal minimum = prices.stream()
                .filter(price -> !price.getPriceDate().isBefore(
                        entry.getPriceDate()
                ))
                .filter(price -> !price.getPriceDate().isAfter(
                        end.getPriceDate()
                ))
                .map(DailyPrice::getClosePrice)
                .min(BigDecimal::compareTo)
                .orElse(entryValue);
        return new HerdEpisodeHorizonOutcome(
                weeks,
                "COMPLETE",
                end.getPriceDate(),
                returnPct,
                percentChange(minimum, entryValue)
        );
    }

    private HerdEpisodeStudyResponse response(
            String ticker,
            String stage,
            List<HerdEpisodeOutcome> episodes
    ) {
        List<HerdEpisodeHorizonSummary> summaries = new ArrayList<>();
        int maximumCompleted = 0;
        for (int weeks : HORIZON_WEEKS) {
            List<HerdEpisodeHorizonOutcome> complete = episodes.stream()
                    .flatMap(episode -> episode.horizons().stream())
                    .filter(outcome -> outcome.weeks() == weeks)
                    .filter(outcome -> "COMPLETE".equals(outcome.status()))
                    .toList();
            maximumCompleted = Math.max(maximumCompleted, complete.size());
            summaries.add(summarize(weeks, complete));
        }
        String evidenceStatus = maximumCompleted >= MINIMUM_COMPLETED_EPISODES
                ? "DESCRIPTIVE_ONLY"
                : "INSUFFICIENT_SAMPLE";
        return new HerdEpisodeStudyResponse(
                "AVAILABLE",
                evidenceStatus,
                ticker,
                stage,
                STATE_MODEL_VERSION,
                MINIMUM_COMPLETED_EPISODES,
                episodes.size(),
                summaries,
                episodes
        );
    }

    private HerdEpisodeHorizonSummary summarize(
            int weeks,
            List<HerdEpisodeHorizonOutcome> outcomes
    ) {
        if (outcomes.isEmpty()) {
            return new HerdEpisodeHorizonSummary(
                    weeks, 0, null, null, null
            );
        }
        List<BigDecimal> returns = outcomes.stream()
                .map(HerdEpisodeHorizonOutcome::returnPct)
                .sorted()
                .toList();
        List<BigDecimal> drawdowns = outcomes.stream()
                .map(HerdEpisodeHorizonOutcome::maxDrawdownPct)
                .sorted()
                .toList();
        long positives = returns.stream()
                .filter(value -> value.signum() > 0)
                .count();
        return new HerdEpisodeHorizonSummary(
                weeks,
                outcomes.size(),
                median(returns),
                BigDecimal.valueOf(positives)
                        .multiply(BigDecimal.valueOf(100))
                        .divide(
                                BigDecimal.valueOf(outcomes.size()),
                                2,
                                RoundingMode.HALF_UP
                        ),
                median(drawdowns)
        );
    }

    private BigDecimal median(List<BigDecimal> values) {
        int middle = values.size() / 2;
        if (values.size() % 2 == 1) {
            return values.get(middle);
        }
        return values.get(middle - 1)
                .add(values.get(middle))
                .divide(BigDecimal.valueOf(2), 2, RoundingMode.HALF_UP);
    }

    private BigDecimal percentChange(
            BigDecimal value,
            BigDecimal baseline
    ) {
        return value.subtract(baseline)
                .multiply(BigDecimal.valueOf(100))
                .divide(baseline, 2, RoundingMode.HALF_UP);
    }

    private HerdEpisodeStudyResponse unavailable(String ticker) {
        return new HerdEpisodeStudyResponse(
                "UNAVAILABLE",
                "INSUFFICIENT_SAMPLE",
                ticker,
                null,
                STATE_MODEL_VERSION,
                MINIMUM_COMPLETED_EPISODES,
                0,
                List.of(),
                List.of()
        );
    }

    private String normalizeTicker(String rawTicker) {
        if (rawTicker == null || rawTicker.isBlank()) {
            throw new IllegalArgumentException("티커를 입력해주세요.");
        }
        String ticker = rawTicker.trim().toUpperCase(Locale.ROOT);
        if (!ticker.matches(TICKER_PATTERN)) {
            throw new IllegalArgumentException(
                    "올바른 미국 주식 티커 형식이 아닙니다."
            );
        }
        return ticker;
    }
}
