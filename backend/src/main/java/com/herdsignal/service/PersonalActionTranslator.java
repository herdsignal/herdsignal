package com.herdsignal.service;

import com.herdsignal.domain.InvestorProfile;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/** 시장 판단이 끝난 뒤 개인 조건으로 행동 비율의 상한만 번역한다. */
@Service
public class PersonalActionTranslator {

    public Translation translate(
            double marketRatio,
            String marketLabel,
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
        boolean buySide = herdScore <= 40.0;
        String label = marketLabel;

        if (horizon < 3) {
            cap = Math.min(cap, 0.05);
            warnings.add("투자 기간이 3년 미만이라 1회 행동 비율을 5% 이내로 제한합니다.");
        }
        switch (strategy) {
            case "NEW_ENTRY" -> {
                cap = Math.min(cap, 0.10);
                if (buySide) label = "분할 진입 " + (marketRatio > 0 ? "확인" : "대기");
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

        double ratio = BigDecimal.valueOf(Math.min(marketRatio, cap))
                .setScale(2, RoundingMode.HALF_UP)
                .doubleValue();
        return new Translation(
                ratio,
                label,
                strategy,
                strategyLabel(strategy),
                String.format("%s · %s 위험 허용도 · 최대 %.0f%%",
                        strategyLabel(strategy), risk, cap * 100),
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

    public record Translation(
            double ratio,
            String label,
            String strategy,
            String strategyLabel,
            String reason,
            List<String> warnings
    ) {
    }
}
