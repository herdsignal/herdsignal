package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/** Action Layer가 참조하는 장기 추세 품질을 계산한다. 매매 방향은 결정하지 않는다. */
final class HerdTrendQualityCalculator {

    Result calculate(HerdIndicator indicator) {
        if (indicator == null) {
            return new Result(35, 50.0, List.of("지표 분해 데이터가 없어 추세 품질을 낮게 반영합니다."));
        }

        int score = 0;
        double ma200DeviationValue = 50.0;
        List<String> warnings = new ArrayList<>();

        BigDecimal ma200Weekly = indicator.getMa200Weekly();
        if (ma200Weekly != null) {
            double value = ma200Weekly.doubleValue();
            score += value >= 60 ? 25 : value >= 40 ? 17 : 8;
        } else {
            warnings.add("200주 MA 위치 데이터가 없습니다.");
        }

        BigDecimal ma200Deviation = indicator.getMa200Deviation();
        if (ma200Deviation != null) {
            double value = ma200Deviation.doubleValue();
            ma200DeviationValue = value;
            score += value >= 35 && value <= 70 ? 20 : value >= 20 && value < 85 ? 14 : 6;
            if (value >= 85) warnings.add("MA200 이격도가 높아 과밀 국면일 수 있습니다.");
            if (value <= 15) warnings.add("MA200 이격도가 낮아 추세 훼손 여부 확인이 필요합니다.");
        }

        BigDecimal position52w = indicator.getPosition52w();
        if (position52w != null) {
            double value = position52w.doubleValue();
            score += value >= 55 ? 20 : value >= 35 ? 14 : 6;
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

        return new Result(Math.max(0, Math.min(100, score)), ma200DeviationValue, List.copyOf(warnings));
    }

    record Result(int score, double ma200Deviation, List<String> warnings) {
    }
}
