package com.herdsignal.service;

/** HERD 상태·추세·변화량을 기존 v6.1 연구 regime으로 번역한다. */
final class HerdRegimePolicy {
    private static final double FLEE_THRESHOLD = 15.0;
    private static final double SCATTER_UPPER = 40.0;
    private static final double DRIFT_LOWER = 60.0;
    private static final double RUSH_THRESHOLD = 75.0;

    ActionDecisionService.RegimeDecision choose(
            double score,
            HerdTrendQualityCalculator.Result trend,
            HerdMomentumCalculator.Result momentum
    ) {
        int trendScore = trend.score();
        double ma200Dev = trend.ma200Deviation();
        boolean rising = momentum.monthDelta() >= 5.0;
        boolean cooling = momentum.monthDelta() <= -3.0 || momentum.shortDelta() <= -3.0;

        if (score >= RUSH_THRESHOLD) {
            if (score >= 90.0) {
                if (cooling || trendScore < 55 || ma200Dev > 90) {
                    return decision("PEAKING_RUSH", "적극 익절 후보", "정점권 군중 밀집", 0.30,
                            "Rush 심화 후 HERD 둔화 또는 추세 부담이 보여 익절 강도를 높입니다.");
                }
                return decision("EXTENDING_RUSH", "분할 익절 후보", "확장형 군중 밀집", 0.18,
                        "HERD가 90 이상이지만 과열이 진행 중이라 전량 대응보다 분할 익절을 우선합니다.");
            }
            if (score >= 85.0) {
                return decision(cooling ? "COOLING_RUSH" : "DEEP_RUSH",
                        cooling ? "익절 우선 후보" : "일부 익절 후보",
                        cooling ? "둔화형 군중 밀집" : "심화형 군중 밀집",
                        cooling ? 0.22 : 0.12,
                        cooling ? "Rush 구간에서 HERD 둔화가 시작돼 익절 비중을 높입니다."
                                : "Rush가 심화 중이지만 추세가 이어져 일부 익절만 제안합니다.");
            }
            if (trendScore >= 75) {
                return decision("HEALTHY_RUSH", "보유 우선·소폭 리밸런싱", "건강한 군중 밀집", 0.05,
                        "강한 추세의 Rush는 전량 대응보다 소폭 리밸런싱이 적합합니다.");
            }
            if (trendScore < 45 || ma200Dev > 90) {
                return decision("CROWDED_RUSH", "적극 익절 후보", "과밀 군중 밀집", 0.30,
                        "추세 품질이 약한 Rush라 과밀 리스크를 크게 반영합니다.");
            }
            return decision("NORMAL_RUSH", "일부 익절 후보", "군중 밀집", rising ? 0.08 : 0.15,
                    rising ? "Rush 초입에서 HERD가 상승 중이라 익절은 작게 나눕니다."
                            : "Rush 구간이지만 추세가 완전히 훼손되지는 않아 일부 익절만 제안합니다.");
        }
        if (score >= DRIFT_LOWER) {
            if (trendScore >= 75) {
                return decision("HEALTHY_DRIFT", "보유 우선", "건강한 군중 쏠림", 0.02,
                        "강한 추세의 Drift라 성급한 익절보다 보유를 우선합니다.");
            }
            return decision("NORMAL_DRIFT", "소폭 익절 후보", "군중 쏠림", 0.06,
                    "군중 쏠림 구간으로 포트폴리오 비중을 가볍게 점검합니다.");
        }
        if (score <= FLEE_THRESHOLD) {
            if (score <= 10.0) {
                if (trendScore < 35 && !rising) {
                    return decision("BROKEN_DEEP_FLEE", "하락 훼손 관찰", "깊은 군중 이탈", 0.0,
                            "Flee가 깊지만 추세와 HERD 변화가 모두 약해 매수보다 관찰을 우선합니다.");
                }
                return decision(rising ? "REVERSING_DEEP_FLEE" : "DEEP_FLEE",
                        rising ? "적극 추가매수 후보" : "분할매수 후보",
                        rising ? "반등형 군중 이탈" : "심화형 군중 이탈", rising ? 0.30 : 0.15,
                        rising ? "깊은 Flee 이후 HERD가 되돌아와 추가매수 강도를 높입니다."
                                : "깊은 Flee지만 아직 반등 확인 전이라 분할매수로 제한합니다.");
            }
            if (trendScore >= 55) {
                return decision("OPPORTUNITY_FLEE", "적극 추가매수 후보", "기회형 군중 이탈", 0.22,
                        "군중 이탈이지만 장기 추세 품질이 유지돼 추가매수 후보로 봅니다.");
            }
            if (trendScore < 35) {
                return decision("BROKEN_FLEE", "하락 훼손 관찰", "훼손형 군중 이탈", 0.0,
                        "낮은 HERD와 약한 추세가 겹쳐 매수보다 관찰을 우선합니다.");
            }
            return decision("NORMAL_FLEE", "소액 분할매수 후보", "군중 이탈", 0.08,
                    "Flee 구간이지만 추세 확인이 더 필요해 소액 분할매수만 제안합니다.");
        }
        if (score <= SCATTER_UPPER) {
            if (score <= 25.0 && trendScore >= 60 && rising) {
                return decision("REVERSING_SCATTER", "분할 추가매수 후보", "회복형 군중 흩어짐", 0.08,
                        "Scatter 저점권에서 HERD 회복이 보여 분할매수 후보로 봅니다.");
            }
            if (trendScore >= 60) {
                return decision("OPPORTUNITY_SCATTER", "분할 추가매수 후보", "기회형 군중 흩어짐", 0.04,
                        "군중 흩어짐 구간에서 장기 추세가 유지돼 분할매수 후보입니다.");
            }
            return decision("NORMAL_SCATTER", "관찰 우선", "군중 흩어짐", 0.0,
                    "Scatter 구간이지만 추세 품질이 충분하지 않아 관찰을 우선합니다.");
        }
        return decision("CALM", "보유 유지", "군중 균형", 0.0,
                "HERD가 중립 구간이라 과도한 매매를 피합니다.");
    }

    private ActionDecisionService.RegimeDecision decision(
            String code, String label, String regimeLabel, double ratio, String reason
    ) {
        return new ActionDecisionService.RegimeDecision(code, label, regimeLabel, ratio, reason);
    }
}
