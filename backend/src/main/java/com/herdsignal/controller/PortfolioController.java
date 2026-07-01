package com.herdsignal.controller;

import com.herdsignal.config.AppConstants;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.*;
import com.herdsignal.service.PortfolioService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 포트폴리오 종목 CRUD + 요약/히스토리 API 컨트롤러.
 * MVP에서 userId는 모든 엔드포인트에서 AppConstants.DEFAULT_USER_ID 고정.
 */
@RestController
@RequestMapping("/api/portfolio")
@RequiredArgsConstructor
public class PortfolioController {

    private final PortfolioService portfolioService;

    /**
     * GET /api/portfolio
     * 보유 종목 전체 목록 조회.
     */
    @GetMapping
    public ResponseEntity<ApiResponse<List<UserPortfolio>>> getPortfolio() {
        List<UserPortfolio> portfolio = portfolioService.getPortfolio(AppConstants.DEFAULT_USER_ID);
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
        portfolioService.addStock(AppConstants.DEFAULT_USER_ID, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(null));
    }

    /**
     * DELETE /api/portfolio/{ticker}
     * 종목 삭제. 없으면 404 Not Found.
     * 204 No Content 반환.
     */
    @DeleteMapping("/{ticker}")
    public ResponseEntity<Void> removeStock(@PathVariable String ticker) {
        portfolioService.removeStock(AppConstants.DEFAULT_USER_ID, ticker);
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
                portfolioService.getPortfolioSummary(AppConstants.DEFAULT_USER_ID);
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
                portfolioService.getPortfolioHistory(AppConstants.DEFAULT_USER_ID, period);
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
        portfolioService.updateAvgPrice(AppConstants.DEFAULT_USER_ID, ticker, request);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    /**
     * GET /api/portfolio/realtime
     * yfinance 실시간 현재가 기반 포트폴리오 조회.
     * Python calculate_current_portfolio()를 ProcessBuilder로 호출한다.
     * 타임아웃 30초.
     */
    @GetMapping("/realtime")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getRealtimePortfolio() {
        Map<String, Object> result = portfolioService.getRealtimePortfolio();
        return ResponseEntity.ok(ApiResponse.success(result));
    }
}
