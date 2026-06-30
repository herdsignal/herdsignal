package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.PortfolioHistory;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.*;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.PortfolioHistoryRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * 포트폴리오 비즈니스 로직.
 * - CRUD: user_portfolio 직접 읽기/쓰기
 * - 조회: portfolio_history (Python 스케줄러 저장 결과) + daily_prices 현재가
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PortfolioService {

    private final UserPortfolioRepository     portfolioRepository;
    private final PortfolioHistoryRepository  historyRepository;
    private final DailyPriceRepository        dailyPriceRepository;

    // ──────────────────────────────────────────────
    // 기존 CRUD 메서드
    // ──────────────────────────────────────────────

    /**
     * 포트폴리오 종목 추가.
     * ticker를 대문자로 정규화 후 저장.
     * 이미 존재하면 DuplicateResourceException (HTTP 409).
     */
    @Transactional
    public void addStock(String userId, PortfolioAddRequest request) {
        String ticker = request.getTicker().toUpperCase();

        if (portfolioRepository.existsByUserIdAndTicker(userId, ticker)) {
            throw new com.herdsignal.exception.DuplicateResourceException(
                    ticker + " 종목이 이미 포트폴리오에 있습니다.");
        }

        LocalDateTime now = LocalDateTime.now();
        UserPortfolio portfolio = UserPortfolio.builder()
                .userId(userId)
                .ticker(ticker)
                .avgPrice(request.getAvgPrice())
                .quantity(request.getQuantity())
                .createdAt(now)
                .updatedAt(now)
                .build();

        portfolioRepository.save(portfolio);
    }

    /**
     * 포트폴리오 종목 삭제.
     * 존재하지 않으면 ResourceNotFoundException (HTTP 404).
     */
    @Transactional
    public void removeStock(String userId, String ticker) {
        UserPortfolio portfolio = portfolioRepository
                .findByUserIdAndTicker(userId, ticker.toUpperCase())
                .orElseThrow(() -> new ResourceNotFoundException(
                        ticker.toUpperCase() + " 종목이 포트폴리오에 없습니다."));

        portfolioRepository.delete(portfolio);
    }

    /**
     * 포트폴리오 전체 조회.
     */
    @Transactional(readOnly = true)
    public List<UserPortfolio> getPortfolio(String userId) {
        return portfolioRepository.findByUserId(userId);
    }

    // ──────────────────────────────────────────────
    // 신규 메서드
    // ──────────────────────────────────────────────

    /**
     * 포트폴리오 현재 평가 요약 조회.
     *
     * 총액 데이터 출처: portfolio_history 최신 스냅샷 (Python이 매일 갱신)
     *   - 없으면 user_portfolio + daily_prices로 실시간 계산 (폴백)
     * 일일 등락률: portfolio_history 최신 2개 스냅샷의 total_value 변화율
     * 종목별 데이터: user_portfolio + daily_prices 실시간 조합
     *
     * @param userId 사용자 ID
     * @return 포트폴리오 요약 (총액·수익률·종목 리스트)
     */
    @Transactional(readOnly = true)
    public PortfolioSummaryResponse getPortfolioSummary(String userId) {
        // avg_price·quantity 모두 존재하는 보유 종목만 조회 (관심종목 제외)
        List<UserPortfolio> holdings = portfolioRepository.findByUserId(userId)
                .stream()
                .filter(p -> p.getAvgPrice() != null && p.getQuantity() != null)
                .collect(Collectors.toList());

        // 종목별 현재가 + 등락률 계산
        List<StockHoldingResponse> stocks = holdings.stream()
                .map(holding -> buildStockHolding(holding))
                .filter(Objects::nonNull)
                .collect(Collectors.toList());

        // 총액 집계: portfolio_history 최신 스냅샷 우선 사용
        BigDecimal totalValue;
        BigDecimal totalCost;
        BigDecimal totalReturnPct;
        BigDecimal dailyChangePct;

        Optional<PortfolioHistory> latestOpt =
                historyRepository.findTopByUserIdOrderBySnapshotDateDesc(userId);

        if (latestOpt.isPresent()) {
            PortfolioHistory latest = latestOpt.get();
            totalValue     = latest.getTotalValue();
            totalCost      = latest.getTotalCost();
            totalReturnPct = latest.getTotalReturnPct();

            // 일일 등락률: 최신 2개 스냅샷의 total_value 변화율
            List<PortfolioHistory> recent =
                    historyRepository.findTop2ByUserIdOrderBySnapshotDateDesc(userId);
            if (recent.size() >= 2) {
                BigDecimal todayValue = recent.get(0).getTotalValue();
                BigDecimal prevValue  = recent.get(1).getTotalValue();
                dailyChangePct = prevValue.compareTo(BigDecimal.ZERO) != 0
                        ? todayValue.subtract(prevValue)
                               .divide(prevValue, 4, RoundingMode.HALF_UP)
                               .multiply(BigDecimal.valueOf(100))
                        : BigDecimal.ZERO;
            } else {
                dailyChangePct = BigDecimal.ZERO;
            }

        } else {
            // 폴백: portfolio_history 없으면 종목 리스트에서 직접 계산
            log.warn("[{}] portfolio_history 없음 — 실시간 계산으로 폴백", userId);
            totalValue = stocks.stream()
                    .map(StockHoldingResponse::getMarketValue)
                    .reduce(BigDecimal.ZERO, BigDecimal::add);
            totalCost = holdings.stream()
                    .filter(h -> h.getAvgPrice() != null && h.getQuantity() != null)
                    .map(h -> h.getAvgPrice().multiply(h.getQuantity()))
                    .reduce(BigDecimal.ZERO, BigDecimal::add);
            totalReturnPct = totalCost.compareTo(BigDecimal.ZERO) > 0
                    ? totalValue.subtract(totalCost)
                            .divide(totalCost, 4, RoundingMode.HALF_UP)
                            .multiply(BigDecimal.valueOf(100))
                    : BigDecimal.ZERO;
            dailyChangePct = BigDecimal.ZERO;
        }

        return PortfolioSummaryResponse.builder()
                .totalValue(totalValue.setScale(2, RoundingMode.HALF_UP))
                .totalCost(totalCost.setScale(2, RoundingMode.HALF_UP))
                .totalReturnPct(totalReturnPct.setScale(2, RoundingMode.HALF_UP))
                .dailyChangePct(dailyChangePct.setScale(2, RoundingMode.HALF_UP))
                .stocks(stocks)
                .build();
    }

    /**
     * 포트폴리오 히스토리 조회.
     *
     * @param userId 사용자 ID
     * @param period "month" → 최근 30일 / "year" → 최근 365일 (기본 month)
     * @return 날짜별 총 평가금액·수익률 시계열
     */
    @Transactional(readOnly = true)
    public PortfolioHistoryResponse getPortfolioHistory(String userId, String period) {
        LocalDate end   = LocalDate.now();
        LocalDate start = "year".equalsIgnoreCase(period)
                ? end.minusDays(365)
                : end.minusDays(30);

        List<PortfolioHistory> histories =
                historyRepository.findByUserIdAndSnapshotDateBetweenOrderBySnapshotDateAsc(
                        userId, start, end);

        List<PortfolioHistoryResponse.HistoryPoint> points = histories.stream()
                .map(h -> PortfolioHistoryResponse.HistoryPoint.builder()
                        .date(h.getSnapshotDate())
                        .totalValue(h.getTotalValue())
                        .totalReturnPct(h.getTotalReturnPct())
                        .build())
                .collect(Collectors.toList());

        return PortfolioHistoryResponse.builder()
                .points(points)
                .build();
    }

    /**
     * 평균 매수가·보유 수량 수정.
     * 존재하지 않는 종목이면 ResourceNotFoundException (HTTP 404).
     *
     * @param userId  사용자 ID
     * @param ticker  수정할 티커 심볼
     * @param request 수정할 avgPrice·quantity
     */
    @Transactional
    public void updateAvgPrice(String userId, String ticker, AvgPriceUpdateRequest request) {
        UserPortfolio portfolio = portfolioRepository
                .findByUserIdAndTicker(userId, ticker.toUpperCase())
                .orElseThrow(() -> new ResourceNotFoundException(
                        ticker.toUpperCase() + " 종목이 포트폴리오에 없습니다."));

        portfolio.setAvgPrice(request.getAvgPrice());
        portfolio.setQuantity(request.getQuantity());
        portfolio.setUpdatedAt(LocalDateTime.now());
        // @Transactional dirty checking — save() 불필요
    }

    // ──────────────────────────────────────────────
    // 내부 헬퍼
    // ──────────────────────────────────────────────

    /**
     * 보유 종목 1개의 현재가·평가금액·등락률을 계산해 DTO로 반환.
     * daily_prices가 없거나 종가가 null이면 null 반환 (스트림에서 제외됨).
     */
    private StockHoldingResponse buildStockHolding(UserPortfolio holding) {
        List<DailyPrice> prices =
                dailyPriceRepository.findTop2ByTickerOrderByPriceDateDesc(holding.getTicker());

        if (prices.isEmpty() || prices.get(0).getClosePrice() == null) {
            log.warn("[{}] daily_prices 종가 없음 — 종목 제외", holding.getTicker());
            return null;
        }

        BigDecimal currentPrice = prices.get(0).getClosePrice();
        BigDecimal avgPrice     = holding.getAvgPrice();
        BigDecimal quantity     = holding.getQuantity();

        BigDecimal marketValue = currentPrice.multiply(quantity);
        BigDecimal returnPct   = currentPrice.subtract(avgPrice)
                .divide(avgPrice, 4, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));

        // 전일 종가가 있으면 일일 등락률 계산, 없으면 0.0
        BigDecimal dailyChangePct = BigDecimal.ZERO;
        if (prices.size() >= 2 && prices.get(1).getClosePrice() != null) {
            BigDecimal prevPrice = prices.get(1).getClosePrice();
            dailyChangePct = currentPrice.subtract(prevPrice)
                    .divide(prevPrice, 4, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100));
        }

        return StockHoldingResponse.builder()
                .ticker(holding.getTicker())
                .avgPrice(avgPrice.setScale(2, RoundingMode.HALF_UP))
                .quantity(quantity.setScale(4, RoundingMode.HALF_UP))
                .currentPrice(currentPrice.setScale(2, RoundingMode.HALF_UP))
                .marketValue(marketValue.setScale(2, RoundingMode.HALF_UP))
                .returnPct(returnPct.setScale(2, RoundingMode.HALF_UP))
                .dailyChangePct(dailyChangePct.setScale(2, RoundingMode.HALF_UP))
                .build();
    }
}
