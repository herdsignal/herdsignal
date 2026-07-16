package com.herdsignal.service;

import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.dto.InvestorProfileRequest;
import com.herdsignal.dto.InvestorProfileResponse;
import com.herdsignal.repository.InvestorProfileRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class InvestorProfileService {
    private static final Set<String> STRATEGIES = Set.of(
            "EXISTING_HOLDER", "NEW_ENTRY", "MONTHLY_DCA", "TARGET_REBALANCE");
    private static final Set<String> RISK_LEVELS = Set.of("CONSERVATIVE", "BALANCED", "GROWTH");
    private static final Set<String> REBALANCE_MODES = Set.of("CONSERVATIVE", "STANDARD", "AGGRESSIVE");

    private final InvestorProfileRepository repository;

    @Transactional
    public InvestorProfileResponse get(String userId) {
        return InvestorProfileResponse.from(repository.findById(userId).orElseGet(() -> repository.save(defaultProfile(userId))));
    }

    @Transactional(readOnly = true)
    public InvestorProfile forDecision(String userId) {
        return repository.findById(userId).orElseGet(() -> defaultProfile(userId));
    }

    @Transactional
    public InvestorProfileResponse update(String userId, InvestorProfileRequest request) {
        validate(request);
        InvestorProfile profile = repository.findById(userId).orElseGet(() -> defaultProfile(userId));
        profile.setStrategy(request.strategy());
        profile.setRiskTolerance(request.riskTolerance());
        profile.setTimeHorizonYears(request.timeHorizonYears());
        profile.setLiquidityBufferMonths(request.liquidityBufferMonths());
        profile.setMaxActionRatio(request.maxActionRatio());
        profile.setTargetEquityRatio(request.targetEquityRatio());
        return InvestorProfileResponse.from(repository.save(profile));
    }

    @Transactional
    public com.herdsignal.dto.RebalanceSettingsResponse updateRebalanceSettings(
            String userId,
            com.herdsignal.dto.RebalanceSettingsRequest request
    ) {
        if (request == null || request.budget() == null
                || request.budget().compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException("리밸런싱 예산은 0 이상이어야 합니다.");
        }
        if (!between(request.cashTargetRatio(), BigDecimal.ZERO, BigDecimal.ONE)) {
            throw new IllegalArgumentException("현금 목표 비중은 0~100%여야 합니다.");
        }
        String mode = request.mode() == null ? "" : request.mode().trim().toUpperCase();
        if (!REBALANCE_MODES.contains(mode)) {
            throw new IllegalArgumentException("지원하지 않는 리밸런싱 모드입니다.");
        }
        InvestorProfile profile = repository.findById(userId).orElseGet(() -> defaultProfile(userId));
        profile.setRebalanceBudget(request.budget().setScale(2, java.math.RoundingMode.HALF_UP));
        profile.setCashTargetRatio(request.cashTargetRatio());
        profile.setRebalanceMode(mode);
        return com.herdsignal.dto.RebalanceSettingsResponse.from(repository.save(profile));
    }

    private void validate(InvestorProfileRequest request) {
        if (request == null || !STRATEGIES.contains(request.strategy())) {
            throw new IllegalArgumentException("지원하지 않는 투자 방식입니다.");
        }
        if (!RISK_LEVELS.contains(request.riskTolerance())) {
            throw new IllegalArgumentException("지원하지 않는 위험 허용도입니다.");
        }
        if (request.timeHorizonYears() == null || request.timeHorizonYears() < 1 || request.timeHorizonYears() > 50) {
            throw new IllegalArgumentException("투자 기간은 1~50년이어야 합니다.");
        }
        if (request.liquidityBufferMonths() == null || request.liquidityBufferMonths() < 0 || request.liquidityBufferMonths() > 60) {
            throw new IllegalArgumentException("생활비 여유는 0~60개월이어야 합니다.");
        }
        if (!between(request.maxActionRatio(), new BigDecimal("0.01"), new BigDecimal("0.30"))) {
            throw new IllegalArgumentException("1회 최대 행동비율은 1~30%여야 합니다.");
        }
        if (!between(request.targetEquityRatio(), new BigDecimal("0.10"), BigDecimal.ONE)) {
            throw new IllegalArgumentException("목표 주식비중은 10~100%여야 합니다.");
        }
    }

    private boolean between(BigDecimal value, BigDecimal minimum, BigDecimal maximum) {
        return value != null && value.compareTo(minimum) >= 0 && value.compareTo(maximum) <= 0;
    }

    private InvestorProfile defaultProfile(String userId) {
        return InvestorProfile.builder()
                .userId(userId).strategy("EXISTING_HOLDER").riskTolerance("BALANCED")
                .timeHorizonYears(10).liquidityBufferMonths(6)
                .maxActionRatio(new BigDecimal("0.15")).targetEquityRatio(new BigDecimal("0.70"))
                .rebalanceBudget(new BigDecimal("1000.00"))
                .cashTargetRatio(new BigDecimal("0.10"))
                .rebalanceMode("STANDARD")
                .build();
    }
}
