package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
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

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
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

    private static final ZoneId KST_ZONE = ZoneId.of("Asia/Seoul");
    private static final LocalTime US_MARKET_DAY_START_KST = LocalTime.of(22, 30);

    private final UserPortfolioRepository     portfolioRepository;
    private final PortfolioHistoryRepository  historyRepository;
    private final DailyPriceRepository        dailyPriceRepository;
    private final TickerReadinessService      tickerReadinessService;

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
        String ticker = tickerReadinessService.normalizeAndValidate(request.getTicker());

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
        LocalDate marketSessionDate = currentMarketSessionDateKst();

        // avg_price·quantity 모두 존재하는 보유 종목만 조회 (관심종목 제외)
        List<UserPortfolio> holdings = portfolioRepository.findByUserId(userId)
                .stream()
                .filter(p -> p.getAvgPrice() != null && p.getQuantity() != null)
                .collect(Collectors.toList());

        // 종목별 현재가 + 등락률 계산
        List<StockHoldingResponse> stocks = holdings.stream()
                .map(holding -> buildStockHolding(holding, marketSessionDate))
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

    /**
     * 실시간 포트폴리오 조회.
     *
     * ProcessBuilder로 Python calculate_current_portfolio('local')를 호출하고
     * JSON 결과를 파싱해 반환한다.
     * 타임아웃 30초. 초과하면 프로세스를 강제 종료하고 예외를 던진다.
     *
     * @return Python이 반환한 포트폴리오 Map (total_value, stocks 등)
     */
    public Map<String, Object> getRealtimePortfolio() {
        // 프로젝트 루트: backend/의 부모 디렉터리
        Path projectRoot = Paths.get(System.getProperty("user.dir")).getParent();
        Path pythonExe   = projectRoot.resolve("data/.venv/bin/python3.12");

        // sys.path에 'data/'를 추가해 scheduler 패키지를 찾을 수 있도록 한다
        String script = String.join("\n",
            "import sys, json",
            "sys.path.insert(0, 'data')",
            "from scheduler.herd_scheduler import calculate_current_portfolio",
            "print(json.dumps(calculate_current_portfolio('local')))"
        );

        ProcessBuilder pb = new ProcessBuilder(pythonExe.toString(), "-c", script);
        pb.directory(projectRoot.toFile());  // 프로젝트 루트 기준으로 실행

        try {
            Process process = pb.start();

            // stdout(JSON 결과)과 stderr(Python 로그)를 별도 스레드로 동시 읽기
            // — 단일 스레드로 읽으면 버퍼 풀링으로 인한 데드락 가능
            StringBuilder output = new StringBuilder();
            StringBuilder stderr  = new StringBuilder();

            Thread stdoutReader = new Thread(() -> {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getInputStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        output.append(line).append("\n");
                    }
                } catch (IOException e) {
                    log.warn("[realtime] stdout 읽기 오류: {}", e.getMessage());
                }
            });

            Thread stderrReader = new Thread(() -> {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getErrorStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        stderr.append(line).append("\n");
                    }
                } catch (IOException e) {
                    log.warn("[realtime] stderr 읽기 오류: {}", e.getMessage());
                }
            });

            stdoutReader.start();
            stderrReader.start();

            boolean finished = process.waitFor(30, TimeUnit.SECONDS);

            // 스레드 종료 대기 (최대 5초)
            stdoutReader.join(5_000);
            stderrReader.join(5_000);

            if (!finished) {
                process.destroyForcibly();
                throw new RuntimeException("Python 스크립트 30초 타임아웃");
            }

            int exitCode = process.exitValue();
            String stderrStr = stderr.toString().trim();

            if (exitCode != 0) {
                // 실패 시 stderr 전체를 ERROR 레벨로 출력해 원인 파악
                log.error("[realtime] Python 스크립트 실패 (exit={}):\n{}", exitCode, stderrStr);
                throw new RuntimeException("Python 스크립트 실패 (exit=" + exitCode + "):\n" + stderrStr);
            }
            if (!stderrStr.isEmpty()) {
                log.debug("[realtime] Python 로그:\n{}", stderrStr);
            }

            String outputStr = output.toString().trim();
            if (outputStr.isEmpty()) {
                throw new RuntimeException("Python 스크립트 출력 없음 (exit=" + exitCode + ")");
            }

            // JSON → Map 변환
            ObjectMapper mapper = new ObjectMapper();
            @SuppressWarnings("unchecked")
            Map<String, Object> result = mapper.readValue(outputStr, Map.class);
            return result;

        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            log.error("[realtime] Python 스크립트 실행 실패: {}", e.getMessage(), e);
            throw new RuntimeException("실시간 포트폴리오 계산 실패: " + e.getMessage());
        }
    }

    // ──────────────────────────────────────────────
    // 내부 헬퍼
    // ──────────────────────────────────────────────

    /**
     * KST 22:30 미국장 시작 기준 현재 세션 날짜.
     * 22:30 전에는 직전 미국장 세션을 오늘로 유지한다.
     */
    private LocalDate currentMarketSessionDateKst() {
        LocalDate today = LocalDate.now(KST_ZONE);
        LocalTime now = LocalTime.now(KST_ZONE);
        return now.isBefore(US_MARKET_DAY_START_KST) ? today.minusDays(1) : today;
    }

    /**
     * 보유 종목 1개의 현재가·평가금액·등락률을 계산해 DTO로 반환.
     * daily_prices가 없거나 종가가 null이면 null 반환 (스트림에서 제외됨).
     */
    private StockHoldingResponse buildStockHolding(UserPortfolio holding, LocalDate marketSessionDate) {
        Optional<DailyPrice> currentPriceOpt =
                dailyPriceRepository.findTopByTickerAndPriceDateLessThanEqualAndClosePriceIsNotNullOrderByPriceDateDesc(
                        holding.getTicker(),
                        marketSessionDate
                );

        if (currentPriceOpt.isEmpty()) {
            log.warn("[{}] daily_prices 종가 없음 — 종목 제외", holding.getTicker());
            return null;
        }

        DailyPrice currentDailyPrice = currentPriceOpt.get();
        BigDecimal currentPrice = currentDailyPrice.getClosePrice();
        BigDecimal avgPrice     = holding.getAvgPrice();
        BigDecimal quantity     = holding.getQuantity();

        BigDecimal marketValue = currentPrice.multiply(quantity);
        BigDecimal returnPct   = currentPrice.subtract(avgPrice)
                .divide(avgPrice, 4, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));

        // 새 미국장 세션 가격이 아직 없으면 0.0으로 초기화 상태 유지
        BigDecimal dailyChangePct = BigDecimal.ZERO;
        if (!currentDailyPrice.getPriceDate().isBefore(marketSessionDate)) {
            Optional<DailyPrice> prevPriceOpt =
                    dailyPriceRepository.findTopByTickerAndPriceDateLessThanAndClosePriceIsNotNullOrderByPriceDateDesc(
                            holding.getTicker(),
                            currentDailyPrice.getPriceDate()
                    );
            if (prevPriceOpt.isPresent()) {
                BigDecimal prevPrice = prevPriceOpt.get().getClosePrice();
                dailyChangePct = currentPrice.subtract(prevPrice)
                        .divide(prevPrice, 4, RoundingMode.HALF_UP)
                        .multiply(BigDecimal.valueOf(100));
            }
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
