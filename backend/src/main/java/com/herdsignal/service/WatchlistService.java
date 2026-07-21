package com.herdsignal.service;

import com.herdsignal.domain.UserWatchlist;
import com.herdsignal.dto.HerdScoreResponse;
import com.herdsignal.dto.WatchlistAddRequest;
import com.herdsignal.dto.WatchlistHerdResponse;
import com.herdsignal.exception.DuplicateResourceException;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.UserWatchlistRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 관심 종목 관리 비즈니스 로직.
 * user_watchlist 테이블에 대한 CRUD를 담당.
 * HERD 조회는 HerdService를 재사용.
 */
@Service
@RequiredArgsConstructor
public class WatchlistService {

    private final UserWatchlistRepository watchlistRepository;
    private final HerdService herdService;
    private final TickerReadinessService tickerReadinessService;

    /**
     * 관심 종목 추가.
     * ticker를 대문자로 정규화 후 저장.
     * 이미 존재하면 DuplicateResourceException 발생 (HTTP 409).
     *
     * @param userId 인증 사용자의 내부 ID
     * @param request 추가 요청 DTO
     */
    @Transactional
    public void addStock(String userId, WatchlistAddRequest request) {
        String ticker = tickerReadinessService.normalizeAndValidate(request.getTicker());

        if (watchlistRepository.existsByUserIdAndTicker(userId, ticker)) {
            throw new DuplicateResourceException(ticker + " 종목이 이미 관심 종목에 있습니다.");
        }

        UserWatchlist watchlist = UserWatchlist.builder()
                .userId(userId)
                .ticker(ticker)
                .memo(request.getMemo())
                .createdAt(LocalDateTime.now())
                .build();

        watchlistRepository.save(watchlist);
    }

    /**
     * 관심 종목 삭제.
     * 존재하지 않으면 ResourceNotFoundException 발생 (HTTP 404).
     *
     * @param userId 인증 사용자의 내부 ID
     * @param ticker 삭제할 티커 심볼
     */
    @Transactional
    public void removeStock(String userId, String ticker) {
        UserWatchlist watchlist = watchlistRepository
                .findByUserIdAndTicker(userId, ticker.toUpperCase())
                .orElseThrow(() -> new ResourceNotFoundException(
                        ticker.toUpperCase() + " 종목이 관심 종목에 없습니다."
                ));

        watchlistRepository.delete(watchlist);
    }

    /**
     * 관심 종목 전체 목록 조회.
     *
     * @param userId 인증 사용자의 내부 ID
     */
    @Transactional(readOnly = true)
    public List<UserWatchlist> getWatchlist(String userId) {
        return watchlistRepository.findByUserId(userId);
    }

    /**
     * 관심 종목 전체 HERD 조회.
     * HerdService.getHerdByTickers()를 재사용해 각 티커의 최신 HERD 데이터를 조회.
     * Python 스케줄러가 미실행된 종목은 결과에서 자동 제외.
     *
     * @param userId 인증 사용자의 내부 ID
     */
    @Transactional(readOnly = true)
    public WatchlistHerdResponse getWatchlistHerd(String userId) {
        List<String> tickers = watchlistRepository.findByUserId(userId).stream()
                .map(UserWatchlist::getTicker)
                .toList();

        List<HerdScoreResponse> herdScores = herdService.getHerdByTickers(tickers, userId);
        return WatchlistHerdResponse.of(herdScores);
    }
}
