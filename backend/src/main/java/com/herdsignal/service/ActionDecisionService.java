package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.dto.ActionDecision;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;

/**
 * HERD Action Layer 계산 서비스.
 * HERD 점수는 시장 상태를, Action Layer는 장기투자자가 움직일 강도를 담당한다.
 */
@Service
public class ActionDecisionService {

    private static final double FLEE_THRESHOLD = 15.0;
    private static final double SCATTER_UPPER = 40.0;
    private static final double DRIFT_LOWER = 60.0;
    private static final double RUSH_THRESHOLD = 75.0;
    private static final String ACTION_MODEL_VERSION = "HERD_v6.1";
    private static final String ACTION_MODEL_NAME = "Validated Progressive Action Layer";
    private static final String BASE_MODEL_VERSION = "HERD_v4";
    private static final String ACTION_MODEL_STATUS = "RESEARCH_VALIDATION";

    public ActionDecision decide(HerdScore score, HerdIndicator indicator, Integer qualityScore) {
        return decide(score, indicator, qualityScore, List.of());
    }

    public ActionDecision decide(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            List<HerdScore> history
    ) {
        return decide(score, indicator, qualityScore, history, null, true);
    }

    public ActionDecision decide(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            List<HerdScore> history,
            InvestorProfile profile,
            boolean currentlyHeld
    ) {
        double rawHerdScore = score.getHerdScore().doubleValue();
        int dataQuality = qualityScore != null ? qualityScore : 50;
        TrendContext trend = calculateTrendContext(indicator);
        MomentumContext momentum = calculateMomentumContext(score, history);
        ScoreContext stabilized = stabilizeScore(rawHerdScore, score.getScoreDate(), history);
        double herdScore = stabilized.score();
        RegimeDecision regime = chooseRegime(herdScore, trend, momentum);
        LifecycleContext lifecycle = calculateLifecycleContext(score, history);
        RegimeDecision adjustedRegime = applyLifecycle(regime, lifecycle, herdScore);
        adjustedRegime = applyConfidence(adjustedRegime, dataQuality, momentum);
        ProfileAdjustment profileAdjustment = applyInvestorProfile(adjustedRegime, profile, currentlyHeld, herdScore);
        adjustedRegime = profileAdjustment.regime();
        int actionScore = calculateActionScore(herdScore, dataQuality, trend.score(), momentum.score(), adjustedRegime);
        actionScore = clamp(actionScore + lifecycle.scoreAdjustment(), 0, 100);

        List<String> reasons = new ArrayList<>();
        reasons.add("HERD " + displayStage(score.getHerdStage()) + " 구간");
        reasons.add("장기 추세 품질 " + trend.score() + "/100");
        reasons.add(momentum.reason());
        reasons.add(stabilized.reason());
        reasons.add(lifecycle.reason());
        reasons.add("데이터 품질 " + dataQuality + "/100");
        reasons.add(adjustedRegime.reason());
        reasons.add(profileAdjustment.reason());

        List<String> warnings = new ArrayList<>(trend.warnings());
        warnings.addAll(momentum.warnings());
        warnings.addAll(lifecycle.warnings());
        warnings.addAll(profileAdjustment.warnings());
        if (dataQuality < 65) {
            warnings.add("데이터 품질이 낮아 행동 비율을 보수적으로 해석해야 합니다.");
        }
        if (adjustedRegime.ratio() == 0.0 && ("Flee".equals(displayStage(score.getHerdStage()))
                || "Scatter".equals(displayStage(score.getHerdStage())))) {
            warnings.add("낮은 HERD 점수지만 추세 훼손 가능성이 있어 관찰을 우선합니다.");
        }

        return ActionDecision.builder()
                .actionModelVersion(ACTION_MODEL_VERSION)
                .actionModelName(ACTION_MODEL_NAME)
                .baseModelVersion(BASE_MODEL_VERSION)
                .actionModelStatus(ACTION_MODEL_STATUS)
                .investorStrategy(profileAdjustment.strategy())
                .investorStrategyLabel(profileAdjustment.strategyLabel())
                .actionScore(actionScore)
                .actionGrade(actionGrade(actionScore, adjustedRegime.ratio()))
                .actionLabel(adjustedRegime.label())
                .actionRatio(BigDecimal.valueOf(adjustedRegime.ratio()).setScale(2, RoundingMode.HALF_UP))
                .actionRegime(adjustedRegime.code())
                .actionRegimeLabel(adjustedRegime.regimeLabel())
                .actionReasons(reasons)
                .actionWarnings(warnings)
                .build();
    }

    private ProfileAdjustment applyInvestorProfile(
            RegimeDecision regime,
            InvestorProfile profile,
            boolean currentlyHeld,
            double herdScore
    ) {
        String strategy = profile == null ? "EXISTING_HOLDER" : profile.getStrategy();
        String risk = profile == null ? "BALANCED" : profile.getRiskTolerance();
        int horizon = profile == null ? 10 : profile.getTimeHorizonYears();
        int liquidity = profile == null ? 6 : profile.getLiquidityBufferMonths();
        double configuredCap = profile == null ? 0.15 : profile.getMaxActionRatio().doubleValue();
        double targetEquityRatio = profile == null ? 0.70 : profile.getTargetEquityRatio().doubleValue();
        double riskCap = switch (risk) {
            case "CONSERVATIVE" -> 0.08;
            case "GROWTH" -> 0.30;
            default -> 0.15;
        };
        double cap = Math.min(configuredCap, riskCap);
        List<String> warnings = new ArrayList<>();
        boolean buySide = herdScore <= SCATTER_UPPER;
        String label = regime.label();

        if (horizon < 3) {
            cap = Math.min(cap, 0.05);
            warnings.add("투자 기간이 3년 미만이라 1회 행동 비율을 5% 이내로 제한합니다.");
        }
        switch (strategy) {
            case "NEW_ENTRY" -> {
                cap = Math.min(cap, 0.10);
                if (buySide) label = "분할 진입 " + (regime.ratio() > 0 ? "확인" : "대기");
                if (!buySide && !currentlyHeld) {
                    cap = 0.0;
                    label = "신규 진입 대기";
                }
            }
            case "MONTHLY_DCA" -> {
                cap = Math.min(cap, 0.05);
                label = buySide ? "정기 적립 우선" : "적립식 비중 점검";
                warnings.add("정기 적립 계획을 기본으로 두고 HERD 행동은 5% 이내 보조 신호로만 봅니다.");
            }
            case "TARGET_REBALANCE" -> {
                cap = Math.min(cap, 0.05);
                label = "목표 비중 확인";
                warnings.add(String.format(
                        "실제 주식 비중이 목표 %.0f%%에서 벗어났을 때만 리밸런싱합니다.",
                        targetEquityRatio * 100));
            }
            default -> {
                if (!currentlyHeld && buySide) {
                    cap = 0.0;
                    label = "기존 보유자 기준·관찰";
                    warnings.add("현재 미보유 종목입니다. 신규 진입자 설정으로 바꿔야 진입 비율을 계산합니다.");
                }
            }
        }

        if (buySide && liquidity < 3) {
            cap = 0.0;
            label = "현금 여유 확보 우선";
            warnings.add("생활비 여유가 3개월 미만이라 추가매수 행동을 보류합니다.");
        }

        double ratio = BigDecimal.valueOf(Math.min(regime.ratio(), cap))
                .setScale(2, RoundingMode.HALF_UP).doubleValue();
        RegimeDecision adjusted = new RegimeDecision(
                regime.code(), label, regime.regimeLabel(), ratio, regime.reason());
        return new ProfileAdjustment(
                adjusted, strategy, strategyLabel(strategy),
                String.format("%s · %s 위험 허용도 · 최대 %.0f%%", strategyLabel(strategy), risk, cap * 100),
                List.copyOf(warnings)
        );
    }

    private String strategyLabel(String strategy) {
        return switch (strategy) {
            case "NEW_ENTRY" -> "신규 진입자";
            case "MONTHLY_DCA" -> "정기 적립식";
            case "TARGET_REBALANCE" -> "목표 비중 리밸런싱";
            default -> "기존 보유자";
        };
    }

    /** 경계 ±2pt에서는 직전 구간을 유지해 하루 단위 신호 뒤집힘을 줄인다. */
    private ScoreContext stabilizeScore(double current, LocalDate latestDate, List<HerdScore> history) {
        HerdScore previous = previousScore(history, latestDate);
        if (previous == null || previous.getHerdScore() == null) {
            return new ScoreContext(current, "단계 안정화 비교 이력 부족");
        }
        double before = previous.getHerdScore().doubleValue();
        double[] boundaries = {FLEE_THRESHOLD, SCATTER_UPPER, DRIFT_LOWER, RUSH_THRESHOLD};
        for (double boundary : boundaries) {
            if (Math.abs(current - boundary) <= 2.0 && (current - boundary) * (before - boundary) < 0) {
                double stable = before < boundary ? boundary - 0.01 : boundary + 0.01;
                return new ScoreContext(stable, String.format("경계 안정화 적용 %.1f→%.1f", before, current));
            }
        }
        return new ScoreContext(current, "단계 안정화 변동 없음");
    }

    /** 데이터와 변화 이력이 약할수록 행동 비율만 축소하고 시장 상태 자체는 보존한다. */
    private RegimeDecision applyConfidence(RegimeDecision regime, int dataQuality, MomentumContext momentum) {
        if (regime.ratio() == 0.0) return regime;
        double qualityFactor = dataQuality >= 85 ? 1.0 : dataQuality >= 65 ? 0.85 : dataQuality >= 50 ? 0.65 : 0.40;
        double historyFactor = momentum.observations() >= 20 ? 1.0 : momentum.observations() >= 5 ? 0.85 : 0.65;
        double ratio = BigDecimal.valueOf(regime.ratio() * qualityFactor * historyFactor)
                .setScale(2, RoundingMode.HALF_UP).doubleValue();
        return new RegimeDecision(regime.code(), regime.label(), regime.regimeLabel(), ratio,
                regime.reason() + String.format(" 신뢰도 보정 %.0f%%를 적용합니다.", qualityFactor * historyFactor * 100));
    }

    private LifecycleContext calculateLifecycleContext(HerdScore latest, List<HerdScore> history) {
        if (latest.getScoreDate() == null || history == null || history.isEmpty()) {
            return new LifecycleContext(0, 1.0, 0, "신호 지속일 데이터 부족", List.of());
        }

        String latestSignal = normalizedSignal(latest.getSignal());
        LocalDate startedAt = latest.getScoreDate();
        for (HerdScore row : history) {
            if (row.getScoreDate() == null || row.getScoreDate().isAfter(latest.getScoreDate())) {
                continue;
            }
            if (normalizedSignal(row.getSignal()).equals(latestSignal)) {
                startedAt = row.getScoreDate();
            } else {
                break;
            }
        }

        long days = Math.max(1, ChronoUnit.DAYS.between(startedAt, latest.getScoreDate()) + 1);
        if (days <= 5) {
            return new LifecycleContext(
                    days,
                    0.65,
                    -8,
                    "신호 초입 " + days + "일째",
                    List.of("초입 신호는 확인 전까지 행동 비율을 낮춥니다.")
            );
        }
        if (days <= 20) {
            return new LifecycleContext(
                    days,
                    1.0,
                    4,
                    "신호 진행 " + days + "일째",
                    List.of()
            );
        }
        if (days <= 45) {
            return new LifecycleContext(
                    days,
                    0.82,
                    -3,
                    "신호 성숙 " + days + "일째",
                    List.of("이미 진행된 신호라 신규 행동은 분할 기준으로 제한합니다.")
            );
        }
        return new LifecycleContext(
                days,
                0.55,
                -10,
                "신호 장기 지속 " + days + "일째",
                List.of("장기 지속 신호는 추격 대응보다 다음 전환 확인이 우선입니다.")
        );
    }

    private RegimeDecision applyLifecycle(RegimeDecision regime, LifecycleContext lifecycle, double herdScore) {
        if (regime.ratio() == 0.0) {
            return regime;
        }

        double adjustedRatio = BigDecimal.valueOf(regime.ratio() * lifecycle.ratioMultiplier())
                .setScale(2, RoundingMode.HALF_UP)
                .doubleValue();

        if (lifecycle.signalDays() <= 5 && adjustedRatio > 0.0) {
            return new RegimeDecision(
                    regime.code() + "_FRESH",
                    freshLabel(regime.label(), herdScore),
                    regime.regimeLabel(),
                    adjustedRatio,
                    regime.reason() + " 단, 신호 초입이라 첫 행동 비율을 낮춥니다."
            );
        }

        if (lifecycle.signalDays() > 45 && adjustedRatio > 0.0) {
            return new RegimeDecision(
                    regime.code() + "_EXTENDED",
                    extendedLabel(regime.label(), herdScore),
                    regime.regimeLabel(),
                    adjustedRatio,
                    regime.reason() + " 다만 오래 지속된 신호라 추격 비중을 제한합니다."
            );
        }

        return new RegimeDecision(
                regime.code(),
                regime.label(),
                regime.regimeLabel(),
                adjustedRatio,
                regime.reason()
        );
    }

    private String freshLabel(String label, double herdScore) {
        if (herdScore <= SCATTER_UPPER) {
            return label.replace("적극 ", "").replace("후보", "확인");
        }
        if (herdScore >= DRIFT_LOWER) {
            return label.replace("적극 ", "").replace("후보", "확인");
        }
        return label;
    }

    private String extendedLabel(String label, double herdScore) {
        if (herdScore <= SCATTER_UPPER) {
            return "추격매수 보류";
        }
        if (herdScore >= DRIFT_LOWER) {
            return "분할 익절 유지";
        }
        return label;
    }

    private MomentumContext calculateMomentumContext(HerdScore latest, List<HerdScore> history) {
        if (history == null || history.size() < 2 || latest.getScoreDate() == null) {
            return new MomentumContext(50, 0.0, 0.0, 0.0, 0, "HERD 변화 데이터 부족", List.of("HERD 변화율 데이터가 부족해 현재 점수 중심으로 해석합니다."));
        }

        HerdScore previous = null;
        HerdScore monthAgo = null;
        LocalDate latestDate = latest.getScoreDate();

        for (HerdScore row : history) {
            if (row.getScoreDate() == null || !row.getScoreDate().isBefore(latestDate)) {
                continue;
            }
            if (previous == null) {
                previous = row;
            }
            long days = ChronoUnit.DAYS.between(row.getScoreDate(), latestDate);
            if (days <= 35) {
                monthAgo = row;
            }
        }

        if (previous == null) {
            return new MomentumContext(50, 0.0, 0.0, 0.0, history.size(), "HERD 변화 데이터 부족", List.of("직전 HERD 포인트가 없어 변화율을 보수적으로 봅니다."));
        }

        HerdScore baseline = monthAgo != null ? monthAgo : previous;
        double shortDelta = latest.getHerdScore().doubleValue() - previous.getHerdScore().doubleValue();
        double monthDelta = latest.getHerdScore().doubleValue() - baseline.getHerdScore().doubleValue();
        HerdScore fiveDay = scoreNearDays(history, latestDate, 5);
        HerdScore twentyDay = scoreNearDays(history, latestDate, 20);
        double fastDelta = fiveDay == null ? shortDelta : latest.getHerdScore().doubleValue() - fiveDay.getHerdScore().doubleValue();
        double slowDelta = twentyDay == null ? monthDelta : latest.getHerdScore().doubleValue() - twentyDay.getHerdScore().doubleValue();
        double acceleration = fastDelta - (slowDelta / 4.0);

        int momentumScore = 50;
        if (monthDelta >= 12) momentumScore = 85;
        else if (monthDelta >= 5) momentumScore = 70;
        else if (monthDelta <= -12) momentumScore = 15;
        else if (monthDelta <= -5) momentumScore = 30;

        String direction = monthDelta > 1
                ? "상승"
                : monthDelta < -1 ? "둔화" : "유지";
        String reason = String.format("HERD 5일 %.1fpt · 20일 %.1fpt · 가속도 %.1f(%s)", fastDelta, slowDelta, acceleration, direction);
        return new MomentumContext(momentumScore, shortDelta, monthDelta, acceleration, history.size(), reason, List.of());
    }

    private HerdScore previousScore(List<HerdScore> history, LocalDate latestDate) {
        if (history == null) return null;
        return history.stream().filter(row -> row.getScoreDate() != null && row.getHerdScore() != null
                        && (latestDate == null || row.getScoreDate().isBefore(latestDate)))
                .max((a, b) -> a.getScoreDate().compareTo(b.getScoreDate())).orElse(null);
    }

    private HerdScore scoreNearDays(List<HerdScore> history, LocalDate latestDate, int days) {
        LocalDate target = latestDate.minusDays(days);
        return history.stream()
                .filter(row -> row.getScoreDate() != null && row.getHerdScore() != null && row.getScoreDate().isBefore(latestDate))
                .min((a, b) -> Long.compare(Math.abs(ChronoUnit.DAYS.between(a.getScoreDate(), target)), Math.abs(ChronoUnit.DAYS.between(b.getScoreDate(), target))))
                .orElse(null);
    }

    private TrendContext calculateTrendContext(HerdIndicator indicator) {
        if (indicator == null) {
            return new TrendContext(35, 50.0, List.of("지표 분해 데이터가 없어 추세 품질을 낮게 반영합니다."));
        }

        int score = 0;
        double ma200DeviationValue = 50.0;
        List<String> warnings = new ArrayList<>();

        BigDecimal ma200Weekly = indicator.getMa200Weekly();
        if (ma200Weekly != null) {
            double value = ma200Weekly.doubleValue();
            if (value >= 60) score += 25;
            else if (value >= 40) score += 17;
            else score += 8;
        } else {
            warnings.add("200주 MA 위치 데이터가 없습니다.");
        }

        BigDecimal ma200Deviation = indicator.getMa200Deviation();
        if (ma200Deviation != null) {
            double value = ma200Deviation.doubleValue();
            ma200DeviationValue = value;
            if (value >= 35 && value <= 70) score += 20;
            else if (value >= 20 && value < 85) score += 14;
            else score += 6;

            if (value >= 85) {
                warnings.add("MA200 이격도가 높아 과밀 국면일 수 있습니다.");
            }
            if (value <= 15) {
                warnings.add("MA200 이격도가 낮아 추세 훼손 여부 확인이 필요합니다.");
            }
        }

        BigDecimal position52w = indicator.getPosition52w();
        if (position52w != null) {
            double value = position52w.doubleValue();
            if (value >= 55) score += 20;
            else if (value >= 35) score += 14;
            else score += 6;
        }

        BigDecimal sectorMultiplier = indicator.getSectorMultiplier();
        if (sectorMultiplier != null) {
            double value = sectorMultiplier.doubleValue();
            if (value <= 0.95) score += 20;
            else if (value <= 1.00) score += 14;
            else if (value <= 1.05) score += 8;
            else {
                score += 4;
                warnings.add("섹터 대비 상대 강도가 약합니다.");
            }
        } else {
            score += 8;
        }

        BigDecimal epsMultiplier = indicator.getEpsMultiplier();
        if (epsMultiplier != null) {
            double value = epsMultiplier.doubleValue();
            if (value <= 0.95) score += 15;
            else if (value <= 1.00) score += 10;
            else if (value <= 1.05) score += 6;
            else {
                score += 3;
                warnings.add("EPS 서프라이즈 흐름이 약합니다.");
            }
        } else {
            score += 6;
        }

        return new TrendContext(clamp(score, 0, 100), ma200DeviationValue, warnings);
    }

    private RegimeDecision chooseRegime(double score, TrendContext trend, MomentumContext momentum) {
        int trendScore = trend.score();
        double ma200Dev = trend.ma200Deviation();
        boolean momentumRising = momentum.monthDelta() >= 5.0;
        boolean momentumCooling = momentum.monthDelta() <= -3.0 || momentum.shortDelta() <= -3.0;

        if (score >= RUSH_THRESHOLD) {
            if (score >= 90.0) {
                if (momentumCooling || trendScore < 55 || ma200Dev > 90) {
                    return new RegimeDecision(
                            "PEAKING_RUSH",
                            "적극 익절 후보",
                            "정점권 군중 밀집",
                            0.30,
                            "Rush 심화 후 HERD 둔화 또는 추세 부담이 보여 익절 강도를 높입니다."
                    );
                }
                return new RegimeDecision(
                        "EXTENDING_RUSH",
                        "분할 익절 후보",
                        "확장형 군중 밀집",
                        0.18,
                        "HERD가 90 이상이지만 과열이 진행 중이라 전량 대응보다 분할 익절을 우선합니다."
                );
            }
            if (score >= 85.0) {
                return new RegimeDecision(
                        momentumCooling ? "COOLING_RUSH" : "DEEP_RUSH",
                        momentumCooling ? "익절 우선 후보" : "일부 익절 후보",
                        momentumCooling ? "둔화형 군중 밀집" : "심화형 군중 밀집",
                        momentumCooling ? 0.22 : 0.12,
                        momentumCooling
                                ? "Rush 구간에서 HERD 둔화가 시작돼 익절 비중을 높입니다."
                                : "Rush가 심화 중이지만 추세가 이어져 일부 익절만 제안합니다."
                );
            }
            if (trendScore >= 75) {
                return new RegimeDecision(
                        "HEALTHY_RUSH",
                        "보유 우선·소폭 리밸런싱",
                        "건강한 군중 밀집",
                        0.05,
                        "강한 추세의 Rush는 전량 대응보다 소폭 리밸런싱이 적합합니다."
                );
            }
            if (trendScore < 45 || ma200Dev > 90) {
                return new RegimeDecision(
                        "CROWDED_RUSH",
                        "적극 익절 후보",
                        "과밀 군중 밀집",
                        0.30,
                        "추세 품질이 약한 Rush라 과밀 리스크를 크게 반영합니다."
                );
            }
            return new RegimeDecision(
                    "NORMAL_RUSH",
                    "일부 익절 후보",
                    "군중 밀집",
                    momentumRising ? 0.08 : 0.15,
                    momentumRising
                            ? "Rush 초입에서 HERD가 상승 중이라 익절은 작게 나눕니다."
                            : "Rush 구간이지만 추세가 완전히 훼손되지는 않아 일부 익절만 제안합니다."
            );
        }

        if (score >= DRIFT_LOWER) {
            if (trendScore >= 75) {
                return new RegimeDecision(
                        "HEALTHY_DRIFT",
                        "보유 우선",
                        "건강한 군중 쏠림",
                        0.02,
                        "강한 추세의 Drift라 성급한 익절보다 보유를 우선합니다."
                );
            }
            return new RegimeDecision(
                    "NORMAL_DRIFT",
                    "소폭 익절 후보",
                    "군중 쏠림",
                    0.06,
                    "군중 쏠림 구간으로 포트폴리오 비중을 가볍게 점검합니다."
            );
        }

        if (score <= FLEE_THRESHOLD) {
            if (score <= 10.0) {
                if (trendScore < 35 && !momentumRising) {
                    return new RegimeDecision(
                            "BROKEN_DEEP_FLEE",
                            "하락 훼손 관찰",
                            "깊은 군중 이탈",
                            0.00,
                            "Flee가 깊지만 추세와 HERD 변화가 모두 약해 매수보다 관찰을 우선합니다."
                    );
                }
                return new RegimeDecision(
                        momentumRising ? "REVERSING_DEEP_FLEE" : "DEEP_FLEE",
                        momentumRising ? "적극 추가매수 후보" : "분할매수 후보",
                        momentumRising ? "반등형 군중 이탈" : "심화형 군중 이탈",
                        momentumRising ? 0.30 : 0.15,
                        momentumRising
                                ? "깊은 Flee 이후 HERD가 되돌아와 추가매수 강도를 높입니다."
                                : "깊은 Flee지만 아직 반등 확인 전이라 분할매수로 제한합니다."
                );
            }
            if (trendScore >= 55) {
                return new RegimeDecision(
                        "OPPORTUNITY_FLEE",
                        "적극 추가매수 후보",
                        "기회형 군중 이탈",
                        0.22,
                        "군중 이탈이지만 장기 추세 품질이 유지돼 추가매수 후보로 봅니다."
                );
            }
            if (trendScore < 35) {
                return new RegimeDecision(
                        "BROKEN_FLEE",
                        "하락 훼손 관찰",
                        "훼손형 군중 이탈",
                        0.00,
                        "낮은 HERD와 약한 추세가 겹쳐 매수보다 관찰을 우선합니다."
                );
            }
            return new RegimeDecision(
                    "NORMAL_FLEE",
                    "소액 분할매수 후보",
                    "군중 이탈",
                    0.08,
                    "Flee 구간이지만 추세 확인이 더 필요해 소액 분할매수만 제안합니다."
            );
        }

        if (score <= SCATTER_UPPER) {
            if (score <= 25.0 && trendScore >= 60 && momentumRising) {
                return new RegimeDecision(
                        "REVERSING_SCATTER",
                        "분할 추가매수 후보",
                        "회복형 군중 흩어짐",
                        0.08,
                        "Scatter 저점권에서 HERD 회복이 보여 분할매수 후보로 봅니다."
                );
            }
            if (trendScore >= 60) {
                return new RegimeDecision(
                        "OPPORTUNITY_SCATTER",
                        "분할 추가매수 후보",
                        "기회형 군중 흩어짐",
                        0.04,
                        "군중 흩어짐 구간에서 장기 추세가 유지돼 분할매수 후보입니다."
                );
            }
            return new RegimeDecision(
                    "NORMAL_SCATTER",
                    "관찰 우선",
                    "군중 흩어짐",
                    0.00,
                    "Scatter 구간이지만 추세 품질이 충분하지 않아 관찰을 우선합니다."
            );
        }

        return new RegimeDecision(
                "CALM",
                "보유 유지",
                "군중 균형",
                0.00,
                "HERD가 중립 구간이라 과도한 매매를 피합니다."
        );
    }

    private int calculateActionScore(
            double herdScore,
            int dataQuality,
            int trendScore,
            int momentumScore,
            RegimeDecision regime
    ) {
        double signalStrength;
        if (herdScore <= SCATTER_UPPER) {
            signalStrength = herdScore <= FLEE_THRESHOLD
                    ? 60.0 + ((FLEE_THRESHOLD - herdScore) / FLEE_THRESHOLD) * 40.0
                    : 40.0 + ((SCATTER_UPPER - herdScore) / (SCATTER_UPPER - FLEE_THRESHOLD)) * 30.0;
            signalStrength = signalStrength * 0.40 + trendScore * 0.30 + momentumScore * 0.15 + dataQuality * 0.15;
        } else if (herdScore >= DRIFT_LOWER) {
            signalStrength = herdScore >= RUSH_THRESHOLD
                    ? 60.0 + ((herdScore - RUSH_THRESHOLD) / (100.0 - RUSH_THRESHOLD)) * 40.0
                    : 40.0 + ((herdScore - DRIFT_LOWER) / (RUSH_THRESHOLD - DRIFT_LOWER)) * 30.0;
            double crowdRisk = signalStrength * ("HEALTHY_RUSH".equals(regime.code()) ? 0.65 : 1.0);
            signalStrength = crowdRisk * 0.42 + (100 - trendScore) * 0.25 + (100 - momentumScore) * 0.18 + dataQuality * 0.15;
        } else {
            signalStrength = 25.0 + dataQuality * 0.20;
        }

        if (regime.ratio() == 0.0) {
            signalStrength = Math.min(signalStrength, 45.0);
        }

        return clamp((int) Math.round(signalStrength), 0, 100);
    }

    private String actionGrade(int score, double ratio) {
        if (ratio == 0.0) return score >= 40 ? "WATCH" : "NO_ACTION";
        if (score >= 80) return "STRONG_ACTION";
        if (score >= 60) return "ACTION";
        if (score >= 40) return "WATCH";
        return "NO_ACTION";
    }

    private String displayStage(String herdStage) {
        if (herdStage == null || herdStage.isBlank()) return "Calm";
        return herdStage.startsWith("Herd ") ? herdStage.substring(5) : herdStage;
    }

    private String normalizedSignal(String signal) {
        return signal == null || signal.isBlank() ? "HOLD" : signal.trim().toUpperCase();
    }

    private int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private record TrendContext(int score, double ma200Deviation, List<String> warnings) {
    }

    private record MomentumContext(
            int score,
            double shortDelta,
            double monthDelta,
            double acceleration,
            int observations,
            String reason,
            List<String> warnings
    ) {
    }

    private record ScoreContext(double score, String reason) {
    }

    private record LifecycleContext(
            long signalDays,
            double ratioMultiplier,
            int scoreAdjustment,
            String reason,
            List<String> warnings
    ) {
    }

    private record RegimeDecision(
            String code,
            String label,
            String regimeLabel,
            double ratio,
            String reason
    ) {
    }

    private record ProfileAdjustment(
            RegimeDecision regime,
            String strategy,
            String strategyLabel,
            String reason,
            List<String> warnings
    ) {
    }
}
