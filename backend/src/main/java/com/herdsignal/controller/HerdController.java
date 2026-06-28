package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.HerdScoreResponse;
import com.herdsignal.dto.PortfolioHerdResponse;
import com.herdsignal.service.HerdService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * HERD Index 조회 API 컨트롤러.
 * 요청 파라미터 수신 → Service 위임 → ApiResponse 반환만 담당.
 */
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class HerdController {

    private final HerdService herdService;

    /**
     * GET /api/portfolio/herd
     * 포트폴리오 전체 종목의 최신 HERD 점수 조회.
     * MVP에서 userId는 "local" 고정.
     */
    @GetMapping("/portfolio/herd")
    public ResponseEntity<ApiResponse<PortfolioHerdResponse>> getPortfolioHerd() {
        PortfolioHerdResponse response = herdService.getPortfolioHerd("local");
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
}
