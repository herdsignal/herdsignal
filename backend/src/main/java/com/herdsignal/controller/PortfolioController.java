package com.herdsignal.controller;

import com.herdsignal.config.AppConstants;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.PortfolioAddRequest;
import com.herdsignal.service.PortfolioService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 포트폴리오 종목 CRUD API 컨트롤러.
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
}
