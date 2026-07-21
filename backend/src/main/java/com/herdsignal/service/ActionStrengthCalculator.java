package com.herdsignal.service;

/** 연구 regime의 행동 강도 표시값을 계산한다. 운영 승인 여부는 다루지 않는다. */
final class ActionStrengthCalculator {
    private static final double FLEE_THRESHOLD = 15.0;
    private static final double SCATTER_UPPER = 40.0;
    private static final double DRIFT_LOWER = 60.0;
    private static final double RUSH_THRESHOLD = 75.0;

    int score(double herdScore, int dataQuality, int trendScore, int momentumScore,
              ActionDecisionService.RegimeDecision regime) {
        double strength;
        if (herdScore <= SCATTER_UPPER) {
            strength = herdScore <= FLEE_THRESHOLD
                    ? 60.0 + (FLEE_THRESHOLD - herdScore) / FLEE_THRESHOLD * 40.0
                    : 40.0 + (SCATTER_UPPER - herdScore) / (SCATTER_UPPER - FLEE_THRESHOLD) * 30.0;
            strength = strength * 0.40 + trendScore * 0.30 + momentumScore * 0.15 + dataQuality * 0.15;
        } else if (herdScore >= DRIFT_LOWER) {
            strength = herdScore >= RUSH_THRESHOLD
                    ? 60.0 + (herdScore - RUSH_THRESHOLD) / (100.0 - RUSH_THRESHOLD) * 40.0
                    : 40.0 + (herdScore - DRIFT_LOWER) / (RUSH_THRESHOLD - DRIFT_LOWER) * 30.0;
            double crowdRisk = strength * ("HEALTHY_RUSH".equals(regime.code()) ? 0.65 : 1.0);
            strength = crowdRisk * 0.42 + (100 - trendScore) * 0.25
                    + (100 - momentumScore) * 0.18 + dataQuality * 0.15;
        } else {
            strength = 25.0 + dataQuality * 0.20;
        }
        if (regime.ratio() == 0.0) strength = Math.min(strength, 45.0);
        return clamp((int) Math.round(strength));
    }

    String grade(int score, double ratio) {
        if (ratio == 0.0) return score >= 40 ? "WATCH" : "NO_ACTION";
        if (score >= 80) return "STRONG_ACTION";
        if (score >= 60) return "ACTION";
        if (score >= 40) return "WATCH";
        return "NO_ACTION";
    }

    Intensity intensity(double ratio) {
        if (ratio <= 0.0) return new Intensity("NONE", "관찰");
        if (ratio <= 0.05) return new Intensity("LOW", "낮음");
        if (ratio <= 0.15) return new Intensity("MEDIUM", "중간");
        return new Intensity("HIGH", "높음");
    }

    private int clamp(int value) {
        return Math.max(0, Math.min(100, value));
    }

    record Intensity(String code, String label) {
    }
}
