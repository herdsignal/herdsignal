package com.herdsignal.controller;

import com.herdsignal.config.AppConstants;
import com.herdsignal.domain.UserWatchlist;
import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.WatchlistAddRequest;
import com.herdsignal.dto.WatchlistHerdResponse;
import com.herdsignal.service.WatchlistService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 관심 종목 CRUD + HERD 조회 API 컨트롤러.
 * MVP에서 userId는 모든 엔드포인트에서 AppConstants.DEFAULT_USER_ID 고정.
 */
@RestController
@RequestMapping("/api/watchlist")
@RequiredArgsConstructor
public class WatchlistController {

    private final WatchlistService watchlistService;

    /**
     * GET /api/watchlist
     * 관심 종목 전체 목록 조회.
     */
    @GetMapping
    public ResponseEntity<ApiResponse<List<UserWatchlist>>> getWatchlist() {
        List<UserWatchlist> watchlist = watchlistService.getWatchlist(AppConstants.DEFAULT_USER_ID);
        return ResponseEntity.ok(ApiResponse.success(watchlist));
    }

    /**
     * GET /api/watchlist/herd
     * 관심 종목 전체의 최신 HERD 점수 조회.
     * HERD 데이터가 없는 종목은 응답에서 제외.
     */
    @GetMapping("/herd")
    public ResponseEntity<ApiResponse<WatchlistHerdResponse>> getWatchlistHerd() {
        WatchlistHerdResponse response = watchlistService.getWatchlistHerd(AppConstants.DEFAULT_USER_ID);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * POST /api/watchlist
     * 관심 종목 추가. 이미 있으면 409 Conflict.
     * 201 Created 반환.
     */
    @PostMapping
    public ResponseEntity<ApiResponse<Void>> addStock(
            @RequestBody WatchlistAddRequest request) {
        watchlistService.addStock(AppConstants.DEFAULT_USER_ID, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(null));
    }

    /**
     * DELETE /api/watchlist/{ticker}
     * 관심 종목 삭제. 없으면 404 Not Found.
     * 204 No Content 반환.
     */
    @DeleteMapping("/{ticker}")
    public ResponseEntity<Void> removeStock(@PathVariable String ticker) {
        watchlistService.removeStock(AppConstants.DEFAULT_USER_ID, ticker);
        return ResponseEntity.noContent().build();
    }
}
