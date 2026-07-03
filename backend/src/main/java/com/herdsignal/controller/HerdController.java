package com.herdsignal.controller;

import com.herdsignal.config.AppConstants;
import com.herdsignal.dto.AnalystResponse;
import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.HerdHistoryResponse;
import com.herdsignal.dto.HerdScoreResponse;
import com.herdsignal.dto.InsiderResponse;
import com.herdsignal.dto.NewsResponse;
import com.herdsignal.dto.PortfolioHerdResponse;
import com.herdsignal.dto.PriceHistoryResponse;
import com.herdsignal.dto.StockFinancialsResponse;
import com.herdsignal.dto.StockSearchResponse;
import com.herdsignal.service.FinancialsService;
import com.herdsignal.service.FinnhubService;
import com.herdsignal.service.HerdService;
import com.herdsignal.service.PriceService;
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
    private final PriceService       priceService;
    private final FinnhubService     finnhubService;

    /**
     * GET /api/stocks/search?q=apple
     * 회사명 또는 티커 기반 종목 심볼 검색 (Finnhub).
     */
    @GetMapping("/stocks/search")
    public ResponseEntity<ApiResponse<StockSearchResponse>> searchStocks(
            @RequestParam String q) {
        StockSearchResponse response = finnhubService.searchStocks(q);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

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
     * POST /api/portfolio/herd/refresh
     * 포트폴리오 전체 종목의 HERD 점수를 강제 재계산 후 조회.
     * 수동 새로고침 전용이며 MVP에서 userId는 AppConstants.DEFAULT_USER_ID 고정.
     */
    @PostMapping("/portfolio/herd/refresh")
    public ResponseEntity<ApiResponse<PortfolioHerdResponse>> refreshPortfolioHerd() {
        PortfolioHerdResponse response = herdService.refreshPortfolioHerd(AppConstants.DEFAULT_USER_ID);
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
     * POST /api/stocks/{ticker}/herd/refresh
     * 특정 종목의 HERD 점수를 강제 재계산 후 조회.
     */
    @PostMapping("/stocks/{ticker}/herd/refresh")
    public ResponseEntity<ApiResponse<HerdScoreResponse>> refreshStockHerd(
            @PathVariable String ticker) {
        HerdScoreResponse response = herdService.refreshStockHerd(ticker.toUpperCase());
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

    /**
     * GET /api/stocks/{ticker}/prices?period=1M
     * 일별 종가 히스토리 조회. period: 1M(기본) | 3M | 1Y | 5Y.
     * daily_prices 테이블 직접 조회 — Python 호출 없음.
     */
    @GetMapping("/stocks/{ticker}/prices")
    public ResponseEntity<ApiResponse<PriceHistoryResponse>> getStockPrices(
            @PathVariable String ticker,
            @RequestParam(defaultValue = "1M") String period) {
        PriceHistoryResponse response = priceService.getPriceHistory(ticker.toUpperCase(), period);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * GET /api/stocks/{ticker}/news
     * 최근 30일 뉴스 최대 5건 조회 (Finnhub).
     * API 실패 또는 키 미설정 시 빈 리스트 반환.
     */
    @GetMapping("/stocks/{ticker}/news")
    public ResponseEntity<ApiResponse<NewsResponse>> getStockNews(@PathVariable String ticker) {
        NewsResponse response = finnhubService.getNews(ticker.toUpperCase());
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * GET /api/stocks/{ticker}/analyst
     * 최신 1개월 애널리스트 추천 컨센서스 조회 (Finnhub).
     * 데이터 없거나 실패 시 data=null 반환.
     */
    @GetMapping("/stocks/{ticker}/analyst")
    public ResponseEntity<ApiResponse<AnalystResponse>> getStockAnalyst(@PathVariable String ticker) {
        AnalystResponse response = finnhubService.getAnalyst(ticker.toUpperCase());
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * GET /api/stocks/{ticker}/insider
     * 최근 내부자 거래 최대 10건 조회 (Finnhub).
     * 실패 시 빈 리스트 반환.
     */
    @GetMapping("/stocks/{ticker}/insider")
    public ResponseEntity<ApiResponse<InsiderResponse>> getStockInsider(@PathVariable String ticker) {
        InsiderResponse response = finnhubService.getInsider(ticker.toUpperCase());
        return ResponseEntity.ok(ApiResponse.success(response));
    }
}
