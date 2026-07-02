package com.herdsignal.controller;

import com.herdsignal.config.AppConstants;
import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.HerdHistoryResponse;
import com.herdsignal.dto.HerdScoreResponse;
import com.herdsignal.dto.PortfolioHerdResponse;
import com.herdsignal.dto.StockFinancialsResponse;
import com.herdsignal.service.FinancialsService;
import com.herdsignal.service.HerdService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * HERD Index 및 종목 데이터 조회 API 컨트롤러.
 * 요청 파라미터 수신 → Service 위임 → ApiResponse 반환만 담당.
 */
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class HerdController {

    private final HerdService        herdService;
    private final FinancialsService  financialsService;

    /**
     * GET /api/portfolio/herd
     * 포트폴리오 전체 종목의 최신 HERD 점수 조회.
     * MVP에서 userId는 AppConstants.DEFAULT_USER_ID 고정.
     */
    @GetMapping("/portfolio/herd")
    public ResponseEntity<ApiResponse<PortfolioHerdResponse>> getPortfolioHerd() {
        PortfolioHerdResponse response = herdService.getPortfolioHerd(AppConstants.DEFAULT_USER_ID);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * GET /api/stocks/{ticker}/herd
     * 특정 종목의 최신 HERD 점수 + 지표 분해값 조회.
     * 데이터가 없으면 404 반환.
     */
    @GetMapping("/stocks/{ticker}/herd")
    public ResponseEntity<ApiResponse<HerdScoreResponse>> getStockHerd(
            @PathVariable String ticker) {
        HerdScoreResponse response = herdService.getStockHerd(ticker.toUpperCase());
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * GET /api/stocks/{ticker}/financials
     * 종목 재무정보 조회 (시가총액·PER·EPS·영업이익률·매출·배당수익률).
     * yfinance .info 기반 on-demand 조회 (Python ProcessBuilder).
     */
    @GetMapping("/stocks/{ticker}/financials")
    public ResponseEntity<ApiResponse<StockFinancialsResponse>> getStockFinancials(
            @PathVariable String ticker) {
        StockFinancialsResponse response = financialsService.getFinancials(ticker.toUpperCase());
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * GET /api/stocks/{ticker}/herd/history?period=3y
     * HERD 점수 히스토리 조회. period 기본값 3y.
     * 지원 형식: 숫자 + y(년) 또는 m(월) — 예: 3y, 1y, 6m.
     */
    @GetMapping("/stocks/{ticker}/herd/history")
    public ResponseEntity<ApiResponse<HerdHistoryResponse>> getStockHerdHistory(
            @PathVariable String ticker,
            @RequestParam(defaultValue = "3y") String period) {
        HerdHistoryResponse response = herdService.getHerdHistory(ticker.toUpperCase(), period);
        return ResponseEntity.ok(ApiResponse.success(response));
    }
}
