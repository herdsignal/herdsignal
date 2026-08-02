package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.Stock;
import com.herdsignal.dto.HerdScoreResponse;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.List;

/** 영속 모델과 계산 결과를 공개 HERD API 계약으로만 변환한다. */
@Component
public class HerdScoreResponseMapper {

    private static final String LEGACY_ACTION_MODEL_VERSION = "HERD_v6.1";
    private static final String LEGACY_ACTION_MODEL_NAME =
            "Validated Progressive Action Layer";
    private static final String LEGACY_ACTION_MODEL_STATUS = "RESEARCH_VALIDATION";

    private final UserActionBoundary actionBoundary;

    public HerdScoreResponseMapper(UserActionBoundary actionBoundary) {
        this.actionBoundary = actionBoundary;
    }

    public HerdScoreResponse map(
            HerdScore score,
            HerdIndicator indicator,
            HerdQualityEvaluator.HerdQuality quality,
            Stock stock,
            HerdScoreResponse.SignalDuration duration
    ) {
        UserActionBoundary.Output action = actionBoundary.locked();
        String legacySignal = normalizeSignal(score.getSignal());

        HerdScoreResponse.HerdScoreResponseBuilder builder = HerdScoreResponse.builder()
                .ticker(score.getTicker())
                .companyName(stock != null ? stock.getName() : null)
                .sector(stock != null ? stock.getSector() : null)
                .logoUrl(stock != null ? stock.getLogoUrl() : null)
                .herdScore(score.getHerdScore())
                .herdBase(score.getHerdScore())
                .epsMultiplier(BigDecimal.ONE)
                .sectorMultiplier(BigDecimal.ONE)
                .herdV4(score.getHerdScore())
                .herdStage(score.getHerdStage())
                .signal(action.action())
                .legacySignal(legacySignal)
                .operationalAction(action.action())
                .actionAuthorized(action.authorized())
                .scoreDate(score.getScoreDate())
                .signalStartedAt(null)
                .signalDurationDays(null)
                .legacySignalStartedAt(duration != null ? duration.getSignalStartedAt() : null)
                .legacySignalDurationDays(duration != null ? duration.getSignalDurationDays() : null)
                .stageStartedAt(duration != null ? duration.getStageStartedAt() : null)
                .stageDurationDays(duration != null ? duration.getStageDurationDays() : null)
                .qualityScore(quality != null ? quality.score() : null)
                .qualityLevel(quality != null ? quality.level() : null)
                .qualityLabel(quality != null ? quality.label() : null)
                .qualitySummary(quality != null ? quality.summary() : null)
                .qualityFlags(quality != null ? quality.flags() : List.of())
                .qualityReasons(quality != null ? quality.reasons() : List.of())
                .operationalModelVersion("HERD_v4")
                .actionModelVersion(LEGACY_ACTION_MODEL_VERSION)
                .actionModelName(LEGACY_ACTION_MODEL_NAME)
                .baseModelVersion("HERD_v4")
                .actionModelStatus(LEGACY_ACTION_MODEL_STATUS)
                .actionDisclaimer("검증되지 않은 Action Layer의 운영 비율은 0%이며 연구 결과만 별도로 제공합니다.")
                .oosValidationSummary("최신 전체 OOS 수치와 채택 게이트 결과는 HERD Lab에서 확인할 수 있습니다.")
                .actionRatio(action.ratio())
                .actionGrade("NO_ACTION")
                .actionLabel("상태 관찰");

        mapIndicator(builder, score, indicator);
        return builder.build();
    }

    private void mapIndicator(
            HerdScoreResponse.HerdScoreResponseBuilder builder,
            HerdScore score,
            HerdIndicator indicator
    ) {
        if (indicator == null) return;
        builder.weeklyRsi(indicator.getWeeklyRsi())
                .monthlyRsi(indicator.getMonthlyRsi())
                .position52w(indicator.getPosition52w())
                .ma200Deviation(indicator.getMa200Deviation())
                .volumeStrength(indicator.getVolumeStrength())
                .ma200Weekly(indicator.getMa200Weekly())
                .herdBase(indicator.getHerdBase() != null
                        ? indicator.getHerdBase()
                        : score.getHerdScore())
                .epsMultiplier(indicator.getEpsMultiplier() != null
                        ? indicator.getEpsMultiplier()
                        : BigDecimal.ONE)
                .sectorMultiplier(indicator.getSectorMultiplier() != null
                        ? indicator.getSectorMultiplier()
                        : BigDecimal.ONE)
                .herdV4(score.getHerdScore());
    }

    private String normalizeSignal(String signal) {
        return signal == null || signal.isBlank()
                ? "HOLD"
                : signal.trim().toUpperCase();
    }
}
