package com.herdsignal.service;

import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.PortfolioAddRequest;
import com.herdsignal.exception.DuplicateResourceException;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 포트폴리오 종목 관리 비즈니스 로직.
 * user_portfolio 테이블에 대해 Spring Boot가 직접 읽기/쓰기를 담당.
 */
@Service
@RequiredArgsConstructor
public class PortfolioService {

    private final UserPortfolioRepository portfolioRepository;

    /**
     * 포트폴리오 종목 추가.
     * ticker를 대문자로 정규화 후 저장.
     * 이미 존재하는 종목이면 DuplicateResourceException 발생 (HTTP 409).
     *
     * @param userId  사용자 ID (MVP: "local")
     * @param request 추가 요청 DTO
     */
    @Transactional
    public void addStock(String userId, PortfolioAddRequest request) {
        String ticker = request.getTicker().toUpperCase();

        if (portfolioRepository.existsByUserIdAndTicker(userId, ticker)) {
            throw new DuplicateResourceException(ticker + " 종목이 이미 포트폴리오에 있습니다.");
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
     * 존재하지 않는 종목이면 ResourceNotFoundException 발생 (HTTP 404).
     *
     * @param userId 사용자 ID (MVP: "local")
     * @param ticker 삭제할 티커 심볼
     */
    @Transactional
    public void removeStock(String userId, String ticker) {
        UserPortfolio portfolio = portfolioRepository
                .findByUserIdAndTicker(userId, ticker.toUpperCase())
                .orElseThrow(() -> new ResourceNotFoundException(
                        ticker.toUpperCase() + " 종목이 포트폴리오에 없습니다."
                ));

        portfolioRepository.delete(portfolio);
    }

    /**
     * 포트폴리오 전체 조회.
     *
     * @param userId 사용자 ID (MVP: "local")
     */
    @Transactional(readOnly = true)
    public List<UserPortfolio> getPortfolio(String userId) {
        return portfolioRepository.findByUserId(userId);
    }
}
