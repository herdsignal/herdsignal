package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.HerdScoreResponse;
import com.herdsignal.dto.PortfolioHerdResponse;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.HerdIndicatorRepository;
import com.herdsignal.repository.HerdScoreRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * HERD Index 조회 비즈니스 로직.
 * Python이 계산·저장한 데이터를 읽어 응답 DTO로 변환한다.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class HerdService {

    private final UserPortfolioRepository portfolioRepository;
    private final HerdScoreRepository herdScoreRepository;
    private final HerdIndicatorRepository herdIndicatorRepository;

    /**
     * 포트폴리오 전체 HERD 조회.
     * 보유 종목별로 최신 HERD 점수 + 지표를 조합해 반환.
     * 포트폴리오가 비어있거나 특정 종목의 데이터가 없으면 빈 리스트 반환 (예외 없음).
     *
     * @param userId 사용자 ID (MVP: "local")
     */
    public PortfolioHerdResponse getPortfolioHerd(String userId) {
        List<UserPortfolio> portfolio = portfolioRepository.findByUserId(userId);

        List<HerdScoreResponse> herdScores = portfolio.stream()
                .map(p -> buildHerdScoreResponse(p.getTicker()))
                .filter(Objects::nonNull)  // 데이터 없는 종목 제외
                .toList();

        return PortfolioHerdResponse.of(herdScores);
    }

    /**
     * 특정 종목 HERD 조회.
     * HERD 점수 데이터가 없으면 ResourceNotFoundException 발생 (HTTP 404).
     *
     * @param ticker 티커 심볼 (대문자)
     */
    public HerdScoreResponse getStockHerd(String ticker) {
        HerdScore score = herdScoreRepository.findTopByTickerOrderByScoreDateDesc(ticker)
                .orElseThrow(() -> new ResourceNotFoundException(
                        ticker + " 종목의 HERD 데이터가 없습니다. Python 스케줄러를 먼저 실행하세요."
                ));

        // 지표 분해값은 없어도 점수만 반환 (null 허용)
        HerdIndicator indicator = herdIndicatorRepository
                .findTopByTickerOrderByScoreDateDesc(ticker)
                .orElse(null);

        return HerdScoreResponse.of(score, indicator);
    }

    /**
     * 티커 목록을 받아 HERD 데이터가 있는 종목만 응답 목록으로 반환.
     * 관심종목·포트폴리오 등 여러 곳에서 재사용.
     * HERD 데이터가 없는 종목은 결과에서 자동 제외 (예외 없음).
     *
     * @param tickers 조회할 티커 심볼 목록
     */
    public List<HerdScoreResponse> getHerdByTickers(List<String> tickers) {
        return tickers.stream()
                .map(this::buildHerdScoreResponse)
                .filter(Objects::nonNull)
                .toList();
    }

    /**
     * 단일 종목의 최신 HerdScoreResponse 생성.
     * 점수 데이터가 없으면 null 반환 (호출부에서 필터링).
     */
    private HerdScoreResponse buildHerdScoreResponse(String ticker) {
        Optional<HerdScore> score = herdScoreRepository.findTopByTickerOrderByScoreDateDesc(ticker);
        if (score.isEmpty()) {
            return null;
        }

        HerdIndicator indicator = herdIndicatorRepository
                .findTopByTickerOrderByScoreDateDesc(ticker)
                .orElse(null);

        return HerdScoreResponse.of(score.get(), indicator);
    }
}
