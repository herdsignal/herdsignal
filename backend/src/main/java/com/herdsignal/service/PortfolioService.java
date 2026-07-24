package com.herdsignal.service;

import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.AvgPriceUpdateRequest;
import com.herdsignal.dto.CashBalanceRequest;
import com.herdsignal.dto.CashBalanceResponse;
import com.herdsignal.dto.PortfolioAddRequest;
import com.herdsignal.dto.PortfolioHistoryResponse;
import com.herdsignal.dto.PortfolioSummaryResponse;
import com.herdsignal.dto.TargetWeightRequest;
import com.herdsignal.exception.DuplicateResourceException;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 포트폴리오 유스케이스의 안정적인 진입점.
 *
 * <p>쓰기 유스케이스는 직접 처리하고, 조회 집계·현금 원장·Python 실행은 각 전용
 * 서비스로 위임한다. 컨트롤러는 이 파사드만 의존하므로 내부 분리가 API 계층으로
 * 전파되지 않는다.</p>
 */
@Service
@RequiredArgsConstructor
public class PortfolioService {

    private final UserPortfolioRepository portfolioRepository;
    private final TickerReadinessService tickerReadinessService;
    private final PortfolioQueryService queryService;
    private final PortfolioCashService cashService;
    private final PortfolioRealtimeRunner realtimeRunner;

    @Transactional
    public void addStock(String userId, PortfolioAddRequest request) {
        String ticker = tickerReadinessService.normalizeAndValidate(request.getTicker());
        if (portfolioRepository.existsByUserIdAndTicker(userId, ticker)) {
            throw new DuplicateResourceException(ticker + " 종목이 이미 포트폴리오에 있습니다.");
        }

        LocalDateTime now = LocalDateTime.now();
        portfolioRepository.save(UserPortfolio.builder()
                .userId(userId)
                .ticker(ticker)
                .avgPrice(request.getAvgPrice())
                .quantity(request.getQuantity())
                .createdAt(now)
                .updatedAt(now)
                .build());
    }

    @Transactional
    public void removeStock(String userId, String ticker) {
        UserPortfolio portfolio = findHolding(userId, ticker);
        portfolioRepository.delete(portfolio);
    }

    @Transactional(readOnly = true)
    public List<UserPortfolio> getPortfolio(String userId) {
        return portfolioRepository.findByUserId(userId);
    }

    public PortfolioSummaryResponse getPortfolioSummary(String userId) {
        return queryService.getSummary(userId);
    }

    public PortfolioHistoryResponse getPortfolioHistory(String userId, String period) {
        return queryService.getHistory(userId, period);
    }

    public CashBalanceResponse getCashBalance(String userId) {
        return cashService.getBalance(userId);
    }

    public CashBalanceResponse updateCashBalance(String userId, CashBalanceRequest request) {
        return cashService.updateBalance(userId, request);
    }

    @Transactional
    public void updateAvgPrice(String userId, String ticker, AvgPriceUpdateRequest request) {
        UserPortfolio portfolio = findHolding(userId, ticker);
        portfolio.setAvgPrice(request.getAvgPrice());
        portfolio.setQuantity(request.getQuantity());
        portfolio.setUpdatedAt(LocalDateTime.now());
    }

    @Transactional
    public void updateTargetWeight(String userId, String ticker, TargetWeightRequest request) {
        validateTargetWeight(request);
        UserPortfolio portfolio = findHolding(userId, ticker);
        portfolio.setTargetWeight(request.targetWeight().setScale(4, RoundingMode.HALF_UP));
        portfolio.setUpdatedAt(LocalDateTime.now());
    }

    public Map<String, Object> getRealtimePortfolio(String userId) {
        return realtimeRunner.calculate(userId);
    }

    private UserPortfolio findHolding(String userId, String ticker) {
        String normalizedTicker = ticker.toUpperCase();
        return portfolioRepository.findByUserIdAndTicker(userId, normalizedTicker)
                .orElseThrow(() -> new ResourceNotFoundException(
                        normalizedTicker + " 종목이 포트폴리오에 없습니다."));
    }

    private void validateTargetWeight(TargetWeightRequest request) {
        BigDecimal targetWeight = request == null ? null : request.targetWeight();
        if (targetWeight == null
                || targetWeight.compareTo(BigDecimal.ZERO) < 0
                || targetWeight.compareTo(BigDecimal.ONE) > 0) {
            throw new IllegalArgumentException("목표 비중은 0~100%여야 합니다.");
        }
    }
}
