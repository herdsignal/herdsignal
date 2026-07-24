package com.herdsignal.dto;

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

    /**
     * 운영 승인된 행동 코드.
     * 하위 호환을 위해 필드명은 signal을 유지하지만, 연구 단계에서는 항상 HOLD다.
     */
    private String signal;

    /** 과거 HERD v4가 점수 구간에서 파생한 연구용 분류. 운영 행동에 사용하지 않는다. */
    private String legacySignal;

    /** 의미가 명시된 운영 행동 코드. signal과 같은 값이다. */
    private String operationalAction;

    /** 운영 행동 비율이 0보다 커 실제 행동이 승인됐는지 여부. */
    private Boolean actionAuthorized;

    /** 점수 산출 기준 날짜 */
    private LocalDate scoreDate;

    /** 현재 승인된 운영 행동이 시작된 날짜. 승인되지 않았으면 null이다. */
    private LocalDate signalStartedAt;

    /** 현재 승인된 운영 행동 지속 일수. 승인되지 않았으면 null이다. */
    private Integer signalDurationDays;

    /** 과거 HERD v4 분류가 시작된 날짜. 연구 상태 관찰에만 사용한다. */
    private LocalDate legacySignalStartedAt;

    /** 과거 HERD v4 분류 지속 일수. 연구 상태 관찰에만 사용한다. */
    private Integer legacySignalDurationDays;

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

    /** 운영 승인된 행동 비율. 연구 단계에서는 항상 0.00이다. */
    private BigDecimal actionRatio;

    /** 연구 비교용 원래 행동 비율. 운영 행동에는 사용하지 않는다. */
    private BigDecimal researchActionRatio;

    /** 연구 비교용 원래 행동 문구. 운영 행동에는 사용하지 않는다. */
    private String researchActionLabel;

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
