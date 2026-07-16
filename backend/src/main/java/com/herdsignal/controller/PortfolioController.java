package com.herdsignal.controller;

import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.*;
import com.herdsignal.service.PortfolioService;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.InvestorProfileService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 포트폴리오 종목 CRUD + 요약/히스토리 API 컨트롤러.
 * 사용자 식별은 현재 로그인 세션에서 가져온다.
 */
@RestController
@RequestMapping("/api/portfolio")
@RequiredArgsConstructor
public class PortfolioController {

    private final PortfolioService portfolioService;
    private final CurrentUserService currentUserService;
    private final InvestorProfileService investorProfileService;

    /**
     * GET /api/portfolio
     * 보유 종목 전체 목록 조회.
     */
    @GetMapping
    public ResponseEntity<ApiResponse<List<UserPortfolio>>> getPortfolio() {
        List<UserPortfolio> portfolio = portfolioService.getPortfolio(currentUserService.requireUserId());
        return ResponseEntity.ok(ApiResponse.success(portfolio));
    }

    /**
     * POST /api/portfolio
     * 종목 추가. 이미 있으면 409 Conflict.
     * 201 Created 반환.
     */
    @PostMapping
    public ResponseEntity<ApiResponse<Void>> addStock(
            @RequestBody PortfolioAddRequest request) {
        portfolioService.addStock(currentUserService.requireUserId(), request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(null));
    }

    /**
     * DELETE /api/portfolio/{ticker}
     * 종목 삭제. 없으면 404 Not Found.
     * 204 No Content 반환.
     */
    @DeleteMapping("/{ticker}")
    public ResponseEntity<Void> removeStock(@PathVariable String ticker) {
        portfolioService.removeStock(currentUserService.requireUserId(), ticker);
        return ResponseEntity.noContent().build();
    }

    /**
     * GET /api/portfolio/summary
     * 포트폴리오 현재 평가 요약 조회.
     * 총 평가금액·수익률·일일 등락률·종목별 상세 반환.
     */
    @GetMapping("/summary")
    public ResponseEntity<ApiResponse<PortfolioSummaryResponse>> getPortfolioSummary() {
        PortfolioSummaryResponse response =
                portfolioService.getPortfolioSummary(currentUserService.requireUserId());
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * GET /api/portfolio/history?period=month
     * 포트폴리오 히스토리 조회.
     * period: "month"(기본, 최근 30일) / "year"(최근 365일)
     */
    @GetMapping("/history")
    public ResponseEntity<ApiResponse<PortfolioHistoryResponse>> getPortfolioHistory(
            @RequestParam(defaultValue = "month") String period) {
        PortfolioHistoryResponse response =
                portfolioService.getPortfolioHistory(currentUserService.requireUserId(), period);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * GET /api/portfolio/cash
     * 현재 현금 보유액 조회.
     */
    @GetMapping("/cash")
    public ResponseEntity<ApiResponse<CashBalanceResponse>> getCashBalance() {
        CashBalanceResponse response =
                portfolioService.getCashBalance(currentUserService.requireUserId());
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * PUT /api/portfolio/cash
     * 현금 보유액 수정. 오늘 현금 스냅샷도 함께 저장한다.
     */
    @PutMapping("/cash")
    public ResponseEntity<ApiResponse<CashBalanceResponse>> updateCashBalance(
            @RequestBody CashBalanceRequest request) {
        CashBalanceResponse response =
                portfolioService.updateCashBalance(currentUserService.requireUserId(), request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * PATCH /api/portfolio/{ticker}/avg-price
     * 평균 매수가·보유 수량 수정.
     * 존재하지 않는 종목이면 404 Not Found.
     */
    @PatchMapping("/{ticker}/avg-price")
    public ResponseEntity<ApiResponse<Void>> updateAvgPrice(
            @PathVariable String ticker,
            @RequestBody AvgPriceUpdateRequest request) {
        portfolioService.updateAvgPrice(currentUserService.requireUserId(), ticker, request);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    @PatchMapping("/{ticker}/target-weight")
    public ResponseEntity<ApiResponse<Void>> updateTargetWeight(
            @PathVariable String ticker,
            @RequestBody TargetWeightRequest request) {
        portfolioService.updateTargetWeight(
                currentUserService.requireUserId(), ticker, request);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    @GetMapping("/rebalance-settings")
    public ResponseEntity<ApiResponse<RebalanceSettingsResponse>> getRebalanceSettings() {
        return ResponseEntity.ok(ApiResponse.success(
                RebalanceSettingsResponse.from(
                        investorProfileService.forDecision(currentUserService.requireUserId()))));
    }

    @PutMapping("/rebalance-settings")
    public ResponseEntity<ApiResponse<RebalanceSettingsResponse>> updateRebalanceSettings(
            @RequestBody RebalanceSettingsRequest request) {
        return ResponseEntity.ok(ApiResponse.success(
                investorProfileService.updateRebalanceSettings(
                        currentUserService.requireUserId(), request)));
    }

    /**
     * GET /api/portfolio/realtime
     * yfinance 실시간 현재가 기반 포트폴리오 조회.
     * Python calculate_current_portfolio()를 ProcessBuilder로 호출한다.
     * 타임아웃 30초.
     */
    @GetMapping("/realtime")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getRealtimePortfolio() {
        Map<String, Object> result = portfolioService.getRealtimePortfolio(currentUserService.requireUserId());
        return ResponseEntity.ok(ApiResponse.success(result));
    }
}
