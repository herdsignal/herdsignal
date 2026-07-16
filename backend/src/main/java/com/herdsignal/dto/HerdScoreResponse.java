package com.herdsignal.dto;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.Stock;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * HERD 점수 + 지표 분해값 합산 응답 DTO.
 * HerdScore(점수·단계·신호) + HerdIndicator(지표값)를 하나로 묶어 반환.
 */
@Getter
@Builder
public class HerdScoreResponse {

    /** 티커 심볼 */
    private String ticker;

    /** 회사명 */
    private String companyName;

    /** 섹터 */
    private String sector;

    /** 회사 로고 URL */
    private String logoUrl;

    /** HERD 점수 (0.00 ~ 100.00) */
    private BigDecimal herdScore;

    /** HERD v3 기본 점수 */
    private BigDecimal herdBase;

    /** EPS 서프라이즈 보정 승수 */
    private BigDecimal epsMultiplier;

    /** 섹터 상대 강도 보정 승수 */
    private BigDecimal sectorMultiplier;

    /** HERD v4 최종 점수 */
    private BigDecimal herdV4;

    /** 단계 (Herd Flee / Scatter / Calm / Drift / Rush) */
    private String herdStage;

    /** 매매 신호 (BUY / SELL / HOLD / ADD / REDUCE) */
    private String signal;

    /** 점수 산출 기준 날짜 */
    private LocalDate scoreDate;

    /** 현재 매매 신호가 시작된 날짜 */
    private LocalDate signalStartedAt;

    /** 현재 매매 신호 지속 일수 */
    private Integer signalDurationDays;

    /** 현재 HERD 단계가 시작된 날짜 */
    private LocalDate stageStartedAt;

    /** 현재 HERD 단계 지속 일수 */
    private Integer stageDurationDays;

    /** HERD 신뢰도 점수 (0~100) */
    private Integer qualityScore;

    /** HERD 신뢰도 등급 (HIGH / GOOD / LIMITED / LOW) */
    private String qualityLevel;

    /** HERD 신뢰도 표시 문구 */
    private String qualityLabel;

    /** HERD 신뢰도 요약 문장 */
    private String qualitySummary;

    /** HERD 신뢰도 플래그 */
    private List<String> qualityFlags;

    /** HERD 신뢰도 산출 근거 */
    private List<String> qualityReasons;

    /** 행동 모델 버전 (HERD_v6 등) */
    private String actionModelVersion;

    /** 행동 모델명 */
    private String actionModelName;

    /** 기반 점수 모델 버전 */
    private String baseModelVersion;

    /** 행동 모델 검증 상태 */
    private String actionModelStatus;

    /** 개인화에 적용된 투자 방식 코드 */
    private String investorStrategy;

    /** 개인화 투자 방식 표시명 */
    private String investorStrategyLabel;

    /** 실서비스에서 점수 상태를 제공하는 운영 모델 */
    private String operationalModelVersion;

    /** Action Layer 사용상 주의 문구 */
    private String actionDisclaimer;

    /** 최신 공개 OOS 검증 요약 */
    private String oosValidationSummary;

    /** 행동 점수 (0~100) */
    private Integer actionScore;

    /** 행동 등급 (STRONG_ACTION / ACTION / WATCH / NO_ACTION) */
    private String actionGrade;

    /** 화면 표시용 행동 문구 */
    private String actionLabel;

    /** 권장 행동 비율 (0.00~0.30) */
    private BigDecimal actionRatio;

    /** 세부 국면 코드 */
    private String actionRegime;

    /** 세부 국면 표시 문구 */
    private String actionRegimeLabel;

    /** 행동 판단 근거 */
    private List<String> actionReasons;

    /** 보수적으로 봐야 하는 이유 */
    private List<String> actionWarnings;

    /** 최근 동일 방향 실제 행동으로 쿨다운이 적용됐는지 여부 */
    private Boolean actionCooldownActive;

    /** 동일 방향 행동까지 남은 거래일 */
    private Integer actionCooldownRemainingDays;

    /** 최근 동일 방향 실제 행동 날짜 */
    private LocalDate lastActionDate;

    /** 현재 총자산 대비 해당 종목 비중 */
    private BigDecimal currentTickerWeight;

    /** 현재 총자산 대비 전체 주식 비중 */
    private BigDecimal currentEquityRatio;

    /** 사용자 목표 주식 비중 */
    private BigDecimal targetEquityRatio;

    private String actionIntensity;

    private String actionIntensityLabel;

    /* ── 지표 분해값 (HerdIndicator로부터, 없으면 null) ── */

    /** 주봉 RSI 백분위 정규화값 */
    private BigDecimal weeklyRsi;

    /** 월봉 RSI 백분위 정규화값 */
    private BigDecimal monthlyRsi;

    /** 52주 고저 위치 백분위 정규화값 */
    private BigDecimal position52w;

    /** MA200 이격도 백분위 정규화값 */
    private BigDecimal ma200Deviation;

    /** 거래량 강도 백분위 정규화값 */
    private BigDecimal volumeStrength;

    /** 200주 MA 위치 백분위 정규화값 */
    private BigDecimal ma200Weekly;

    /**
     * 정적 팩토리 메서드.
     * HerdScore는 필수, HerdIndicator는 없을 수 있으므로 null 허용.
     */
    public static HerdScoreResponse of(HerdScore score, HerdIndicator indicator) {
        return of(score, indicator, null, null, null, null, List.of(), List.of(), null, null, null);
    }

    /**
     * 정적 팩토리 메서드.
     * HERD 신뢰도는 DB 저장값이 아니라 응답 생성 시점에 계산해 함께 내려준다.
     */
    public static HerdScoreResponse of(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            String qualityLevel,
            String qualityLabel,
            String qualitySummary,
            List<String> qualityFlags,
            List<String> qualityReasons,
            ActionDecision actionDecision
    ) {
        return of(
                score,
                indicator,
                qualityScore,
                qualityLevel,
                qualityLabel,
                qualitySummary,
                qualityFlags,
                qualityReasons,
                actionDecision,
                null,
                null
        );
    }

    /**
     * 정적 팩토리 메서드.
     * Stock 메타데이터가 있으면 회사명/섹터/로고 URL을 함께 내려준다.
     */
    public static HerdScoreResponse of(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            String qualityLevel,
            String qualityLabel,
            String qualitySummary,
            List<String> qualityFlags,
            List<String> qualityReasons,
            ActionDecision actionDecision,
            Stock stock
    ) {
        return of(
                score,
                indicator,
                qualityScore,
                qualityLevel,
                qualityLabel,
                qualitySummary,
                qualityFlags,
                qualityReasons,
                actionDecision,
                stock,
                null
        );
    }

    /**
     * 정적 팩토리 메서드.
     * SignalDuration이 있으면 현재 신호/단계 지속 기간을 함께 내려준다.
     */
    public static HerdScoreResponse of(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            String qualityLevel,
            String qualityLabel,
            String qualitySummary,
            List<String> qualityFlags,
            List<String> qualityReasons,
            ActionDecision actionDecision,
            Stock stock,
            SignalDuration signalDuration
    ) {
        HerdScoreResponseBuilder builder = HerdScoreResponse.builder()
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
                .signal(score.getSignal())
                .scoreDate(score.getScoreDate())
                .signalStartedAt(signalDuration != null ? signalDuration.getSignalStartedAt() : null)
                .signalDurationDays(signalDuration != null ? signalDuration.getSignalDurationDays() : null)
                .stageStartedAt(signalDuration != null ? signalDuration.getStageStartedAt() : null)
                .stageDurationDays(signalDuration != null ? signalDuration.getStageDurationDays() : null)
                .qualityScore(qualityScore)
                .qualityLevel(qualityLevel)
                .qualityLabel(qualityLabel)
                .qualitySummary(qualitySummary)
                .qualityFlags(qualityFlags)
                .qualityReasons(qualityReasons);

        builder.operationalModelVersion("HERD_v4")
               .actionDisclaimer("연구 검증 중인 행동 보조 정보이며 확정 매매 추천이 아닙니다.")
               .oosValidationSummary("최신 전체 OOS 수치와 채택 게이트 결과는 HERD Lab에서 확인할 수 있습니다.");

        if (actionDecision != null) {
            builder.actionModelVersion(actionDecision.getActionModelVersion())
                   .actionModelName(actionDecision.getActionModelName())
                   .baseModelVersion(actionDecision.getBaseModelVersion())
                   .actionModelStatus(actionDecision.getActionModelStatus())
                   .investorStrategy(actionDecision.getInvestorStrategy())
                   .investorStrategyLabel(actionDecision.getInvestorStrategyLabel())
                   .actionScore(actionDecision.getActionScore())
                   .actionGrade(actionDecision.getActionGrade())
                   .actionLabel(actionDecision.getActionLabel())
                   .actionRatio(actionDecision.getActionRatio())
                   .actionRegime(actionDecision.getActionRegime())
                   .actionRegimeLabel(actionDecision.getActionRegimeLabel())
                   .actionReasons(actionDecision.getActionReasons())
                   .actionWarnings(actionDecision.getActionWarnings())
                   .actionCooldownActive(actionDecision.getActionCooldownActive())
                   .actionCooldownRemainingDays(actionDecision.getActionCooldownRemainingDays())
                   .lastActionDate(actionDecision.getLastActionDate())
                   .currentTickerWeight(actionDecision.getCurrentTickerWeight())
                   .currentEquityRatio(actionDecision.getCurrentEquityRatio())
                   .targetEquityRatio(actionDecision.getTargetEquityRatio())
                   .actionIntensity(actionDecision.getActionIntensity())
                   .actionIntensityLabel(actionDecision.getActionIntensityLabel());
        }

        // 지표 분해값이 있는 경우에만 채움
        if (indicator != null) {
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

        return builder.build();
    }

    /** 현재 신호/단계 지속 기간 DTO */
    @Getter
    @Builder
    public static class SignalDuration {
        private LocalDate signalStartedAt;
        private Integer signalDurationDays;
        private LocalDate stageStartedAt;
        private Integer stageDurationDays;
    }
}
