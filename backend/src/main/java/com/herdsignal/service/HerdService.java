package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.Stock;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.dto.HerdHistoryPoint;
import com.herdsignal.dto.HerdHistoryResponse;
import com.herdsignal.dto.HerdScoreResponse;
import com.herdsignal.dto.PortfolioHerdResponse;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.HerdIndicatorRepository;
import com.herdsignal.repository.HerdScoreRepository;
import com.herdsignal.repository.StockRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * HERD Index 조회 비즈니스 로직.
 * Python이 계산·저장한 데이터를 읽어 응답 DTO로 변환한다.
 *
 * Tier 1 (스케줄러): 매일 자동 계산된 데이터를 DB에서 직접 조회.
 * Tier 2 (on-demand): DB에 데이터 없으면 Python calculate_on_demand 즉시 실행.
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class HerdService {

    private static final int ACTION_CONTEXT_MONTHS = 13;
    private final UserPortfolioRepository portfolioRepository;
    private final HerdScoreRepository herdScoreRepository;
    private final HerdIndicatorRepository herdIndicatorRepository;
    private final StockRepository stockRepository;
    private final HerdResponseAssembler responseAssembler;
    private final ActionCooldownService actionCooldownService;
    private final PortfolioActionContextService portfolioActionContextService;
    private final InvestorProfileService investorProfileService;
    private final HerdOnDemandRunner onDemandRunner;
    private final UsMarketSessionClock marketSessionClock;

    /**
     * 포트폴리오 전체 HERD 조회.
     * 보유 종목별로 최신 HERD 점수 + 지표를 조합해 반환.
     * 포트폴리오가 비어있거나 특정 종목의 데이터가 없으면 빈 리스트 반환 (예외 없음).
     *
     * @param userId 인증 사용자의 내부 ID
     */
    public PortfolioHerdResponse getPortfolioHerd(String userId) {
        List<UserPortfolio> portfolio = portfolioRepository.findByUserId(userId);
        List<HerdScoreResponse> herdScores = getHerdByTickers(portfolio.stream()
                .map(UserPortfolio::getTicker)
                .toList(), userId);

        return PortfolioHerdResponse.of(herdScores);
    }

    /**
     * 포트폴리오 전체 HERD 강제 갱신.
     * 수동 새로고침 전용 경로로, 보유 종목마다 Python on-demand 계산을 캐시 무시로 실행한 뒤
     * 최신 DB 값을 다시 읽어 반환한다. 일부 종목 실패는 로그만 남기고 나머지 종목 응답은 유지한다.
     *
     * @param userId 인증 사용자의 내부 ID
     */
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public PortfolioHerdResponse refreshPortfolioHerd(String userId) {
        List<UserPortfolio> portfolio = portfolioRepository.findByUserId(userId);

        List<String> tickers = portfolio.stream()
                .map(UserPortfolio::getTicker)
                .filter(Objects::nonNull)
                .distinct()
                .toList();

        if (!tickers.isEmpty()) {
            try {
                onDemandRunner.refreshMany(tickers, true);
            } catch (Exception e) {
                log.error("[portfolio] HERD 배치 강제 갱신 실패: {}", e.getMessage());
                throw new ResourceNotFoundException(
                        "포트폴리오 HERD 강제 갱신 실패: " + e.getMessage()
                );
            }
        }

        List<HerdScoreResponse> herdScores = getHerdByTickers(tickers, userId);

        return PortfolioHerdResponse.of(herdScores);
    }

    /**
     * 특정 종목의 저장된 최신 HERD를 조회한다.
     *
     * <p>GET 요청은 외부 프로세스 실행이나 DB 쓰기를 절대 발생시키지 않는다.
     * 데이터 생성은 인증된 refreshStockHerd 유스케이스에서만 수행한다.</p>
     */
    public HerdScoreResponse getStockHerd(String ticker, String userId) {
        HerdScore score = herdScoreRepository.findTopByTickerOrderByScoreDateDesc(ticker)
                .orElseThrow(() -> new ResourceNotFoundException(
                        ticker + " HERD 데이터가 없습니다. 로그인 후 새로고침을 실행하세요."));

        // 지표 분해값은 없어도 점수만 반환 (null 허용)
        HerdIndicator indicator = herdIndicatorRepository
                .findTopByTickerOrderByScoreDateDesc(ticker)
                .orElse(null);

        return buildResponse(score, indicator, userId);
    }

    /**
     * 특정 종목 HERD 강제 갱신.
     * 캐시가 있어도 Python calculate_on_demand(..., force=True)를 실행한 뒤 DB 최신값을 반환한다.
     *
     * @param ticker 티커 심볼 (대문자)
     */
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public HerdScoreResponse refreshStockHerd(String ticker, String userId) {
        try {
            onDemandRunner.refresh(ticker, true);
        } catch (Exception e) {
            log.error("[{}] Python on-demand 강제 갱신 실패: {}", ticker, e.getMessage());
            throw new ResourceNotFoundException(
                    ticker + " HERD 강제 갱신 실패: " + e.getMessage()
            );
        }

        Optional<HerdScore> scoreOpt =
                herdScoreRepository.findTopByTickerOrderByScoreDateDesc(ticker);
        if (scoreOpt.isEmpty()) {
            throw new ResourceNotFoundException(
                    ticker + " 강제 갱신 완료 후에도 DB에 데이터가 없습니다."
            );
        }

        HerdIndicator indicator = herdIndicatorRepository
                .findTopByTickerOrderByScoreDateDesc(ticker)
                .orElse(null);

        return buildResponse(scoreOpt.get(), indicator, userId);
    }

    /**
     * 티커 목록을 받아 HERD 데이터가 있는 종목만 응답 목록으로 반환.
     * 관심종목·포트폴리오 등 여러 곳에서 재사용.
     * HERD 데이터가 없는 종목은 결과에서 자동 제외 (예외 없음).
     *
     * @param tickers 조회할 티커 심볼 목록
     */
    public List<HerdScoreResponse> getHerdByTickers(List<String> tickers, String userId) {
        List<String> normalizedTickers = tickers.stream()
                .filter(Objects::nonNull)
                .map(String::toUpperCase)
                .distinct()
                .toList();
        if (normalizedTickers.isEmpty()) {
            return List.of();
        }

        Map<String, List<HerdScore>> historyByTicker = herdScoreRepository
                .findContextByTickers(
                        normalizedTickers,
                        marketSessionClock.currentSessionDate().minusMonths(ACTION_CONTEXT_MONTHS))
                .stream()
                .collect(Collectors.groupingBy(
                        HerdScore::getTicker,
                        LinkedHashMap::new,
                        Collectors.toList()
                ));
        Map<String, HerdIndicator> indicatorByTicker = herdIndicatorRepository
                .findLatestByTickers(normalizedTickers)
                .stream()
                .collect(Collectors.toMap(HerdIndicator::getTicker, indicator -> indicator));
        Map<String, Stock> stockByTicker = stockRepository.findByTickerIn(normalizedTickers)
                .stream()
                .collect(Collectors.toMap(Stock::getTicker, stock -> stock));
        InvestorProfile profile = userId == null ? null : investorProfileService.forDecision(userId);
        var heldTickers = userId == null ? java.util.Set.<String>of() : portfolioRepository.findByUserId(userId).stream()
                .map(UserPortfolio::getTicker)
                .collect(Collectors.toSet());
        Map<String, LocalDate> scoreDates = historyByTicker.entrySet().stream()
                .filter(entry -> !entry.getValue().isEmpty())
                .collect(Collectors.toMap(Map.Entry::getKey, entry -> entry.getValue().get(0).getScoreDate()));
        Map<String, ActionCooldownContext> cooldownByTicker = actionCooldownService.getContexts(
                userId, normalizedTickers, scoreDates);
        Map<String, PortfolioActionContext> portfolioContextByTicker =
                portfolioActionContextService.getContexts(userId, normalizedTickers, profile);

        return normalizedTickers.stream()
                .map(ticker -> {
                    List<HerdScore> history = historyByTicker.get(ticker);
                    if (history == null || history.isEmpty()) {
                        return null;
                    }
                    return buildResponse(
                            history.get(0),
                            indicatorByTicker.get(ticker),
                            history,
                            stockByTicker.get(ticker),
                            profile,
                            heldTickers.contains(ticker),
                            cooldownByTicker.getOrDefault(ticker, ActionCooldownContext.none()),
                            portfolioContextByTicker.getOrDefault(
                                    ticker, PortfolioActionContext.unavailable())
                    );
                })
                .filter(Objects::nonNull)
                .toList();
    }

    /**
     * 특정 종목의 HERD 점수 히스토리 조회.
     * period 문자열을 파싱해 기준일을 산출하고 그 이후 데이터를 날짜 오름차순으로 반환.
     *
     * @param ticker 티커 심볼 (대문자)
     * @param period "3y" / "1y" / "6m" 등 — 미지원 형식은 기본값 3y 적용
     */
    public HerdHistoryResponse getHerdHistory(String ticker, String period) {
        LocalDate cutoff = HerdHistoryPeriod.cutoff(
                period,
                marketSessionClock.currentSessionDate());
        List<HerdScore> scores = herdScoreRepository.findHistoryByTickerSince(ticker, cutoff);
        List<HerdHistoryPoint> points = scores.stream()
                .map(s -> HerdHistoryPoint.builder()
                        .date(s.getScoreDate().toString())
                        .score(s.getHerdScore().doubleValue())
                        .build())
                .toList();
        return HerdHistoryResponse.builder().points(points).build();
    }

    /** HERD 점수 응답에 데이터 신뢰도 레이어를 붙인다. */
    private HerdScoreResponse buildResponse(HerdScore score, HerdIndicator indicator, String userId) {
        List<HerdScore> history = herdScoreRepository.findContextByTicker(
                score.getTicker(),
                marketSessionClock.currentSessionDate().minusMonths(ACTION_CONTEXT_MONTHS));
        Stock stock = stockRepository.findByTicker(score.getTicker()).orElse(null);
        InvestorProfile profile = userId == null ? null : investorProfileService.forDecision(userId);
        boolean currentlyHeld = userId != null && portfolioRepository.existsByUserIdAndTicker(
                userId, score.getTicker());
        ActionCooldownContext cooldown = actionCooldownService.getContext(
                userId, score.getTicker(), score.getScoreDate());
        PortfolioActionContext portfolioContext = portfolioActionContextService.getContexts(
                userId, List.of(score.getTicker()), profile)
                .getOrDefault(score.getTicker(), PortfolioActionContext.unavailable());
        return buildResponse(
                score, indicator, history, stock, profile, currentlyHeld, cooldown, portfolioContext);
    }

    /** 이미 일괄 조회한 데이터로 응답을 만들어 목록 API의 N+1 쿼리를 피한다. */
    private HerdScoreResponse buildResponse(
            HerdScore score,
            HerdIndicator indicator,
            List<HerdScore> history,
            Stock stock,
            InvestorProfile profile,
            boolean currentlyHeld,
            ActionCooldownContext cooldown,
            PortfolioActionContext portfolioContext
    ) {
        return responseAssembler.assemble(
                score,
                indicator,
                history,
                stock,
                profile,
                currentlyHeld,
                cooldown,
                portfolioContext
        );
    }
}
