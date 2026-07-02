package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.SpyMarketResponse;
import com.herdsignal.service.MarketService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 시장 레퍼런스 데이터 API 컨트롤러.
 * 요청 수신 → Service 위임 → ApiResponse 반환만 담당.
 */
@RestController
@RequestMapping("/api/market")
@RequiredArgsConstructor
public class MarketController {

    private final MarketService marketService;

    /**
     * GET /api/market/spy
     * SPY 현재가 + 1개월 수익률 조회.
     * yfinance 조회(약 15분 지연)를 Python ProcessBuilder로 실행한다.
     */
    @GetMapping("/spy")
    public ResponseEntity<ApiResponse<SpyMarketResponse>> getSpyMarket() {
        SpyMarketResponse response = marketService.getSpyMarketData();
        return ResponseEntity.ok(ApiResponse.success(response));
    }
}
