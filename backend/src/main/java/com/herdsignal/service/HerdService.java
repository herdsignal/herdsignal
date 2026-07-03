package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.UserPortfolio;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.HerdHistoryPoint;
import com.herdsignal.dto.HerdHistoryResponse;
import com.herdsignal.dto.HerdScoreResponse;
import com.herdsignal.dto.PortfolioHerdResponse;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.HerdIndicatorRepository;
import com.herdsignal.repository.HerdScoreRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.io.IOException;
import java.math.BigDecimal;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.time.LocalDate;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
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
     * 포트폴리오 전체 HERD 강제 갱신.
     * 수동 새로고침 전용 경로로, 보유 종목마다 Python on-demand 계산을 캐시 무시로 실행한 뒤
     * 최신 DB 값을 다시 읽어 반환한다. 일부 종목 실패는 로그만 남기고 나머지 종목 응답은 유지한다.
     *
     * @param userId 사용자 ID (MVP: "local")
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
                triggerPythonOnDemandBatch(tickers, true);
            } catch (Exception e) {
                log.error("[portfolio] HERD 배치 강제 갱신 실패: {}", e.getMessage());
                throw new ResourceNotFoundException(
                        "포트폴리오 HERD 강제 갱신 실패: " + e.getMessage()
                );
            }
        }

        List<HerdScoreResponse> herdScores = portfolio.stream()
                .map(p -> buildHerdScoreResponse(p.getTicker()))
                .filter(Objects::nonNull)
                .toList();

        return PortfolioHerdResponse.of(herdScores);
    }

    /**
     * 특정 종목 HERD 조회 (Tier 1 + Tier 2 통합).
     *
     * DB에 데이터가 있으면 바로 반환 (Tier 1 경로).
     * DB에 데이터가 없으면 Python calculate_on_demand를 ProcessBuilder로 실행 후
     * DB에 저장된 결과를 재조회해 반환 (Tier 2 경로).
     *
     * NOT_SUPPORTED 사용 이유:
     * Python 프로세스는 자체 커넥션으로 DB에 직접 커밋한다.
     * Spring 트랜잭션(REPEATABLE READ)이 살아있으면 재조회 시 Python 커밋 전
     * 스냅샷이 보여 데이터를 찾지 못한다 → 트랜잭션 없이 각 쿼리가
     * 별도 커넥션을 사용하도록 NOT_SUPPORTED 적용.
     *
     * @param ticker 티커 심볼 (대문자)
     */
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public HerdScoreResponse getStockHerd(String ticker) {
        // ── 1. DB 조회 (Tier 1: 스케줄러가 미리 계산한 데이터) ────────────
        Optional<HerdScore> scoreOpt =
                herdScoreRepository.findTopByTickerOrderByScoreDateDesc(ticker);

        if (scoreOpt.isEmpty()) {
            // ── 2. 데이터 없음 → Python on-demand 계산 (Tier 2) ───────────
            log.info("[{}] DB에 HERD 데이터 없음 → Python on-demand 계산 시작", ticker);
            try {
                triggerPythonOnDemand(ticker);
            } catch (Exception e) {
                log.error("[{}] Python on-demand 실패: {}", ticker, e.getMessage());
                throw new ResourceNotFoundException(
                        ticker + " HERD 계산 실패: " + e.getMessage()
                );
            }

            // ── 3. Python 커밋 후 DB 재조회 ──────────────────────────────
            scoreOpt = herdScoreRepository.findTopByTickerOrderByScoreDateDesc(ticker);
            if (scoreOpt.isEmpty()) {
                throw new ResourceNotFoundException(
                        ticker + " on-demand 계산 완료 후에도 DB에 데이터가 없습니다."
                );
            }
        }

        // 지표 분해값은 없어도 점수만 반환 (null 허용)
        HerdIndicator indicator = herdIndicatorRepository
                .findTopByTickerOrderByScoreDateDesc(ticker)
                .orElse(null);

        return buildResponse(scoreOpt.get(), indicator);
    }

    /**
     * 특정 종목 HERD 강제 갱신.
     * 캐시가 있어도 Python calculate_on_demand(..., force=True)를 실행한 뒤 DB 최신값을 반환한다.
     *
     * @param ticker 티커 심볼 (대문자)
     */
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public HerdScoreResponse refreshStockHerd(String ticker) {
        try {
            triggerPythonOnDemand(ticker, true);
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

        return buildResponse(scoreOpt.get(), indicator);
    }

    /**
     * ProcessBuilder로 Python calculate_on_demand(ticker)를 실행한다.
     * 프로세스가 정상 종료(exit 0)되면 DB에 결과가 저장되어 있음.
     *
     * 프로젝트 루트 탐색: data/ 디렉토리가 있는 경로를 working directory로 설정.
     * 타임아웃: 30초 초과 시 프로세스 강제 종료 후 예외 발생.
     *
     * @param ticker 유효성이 검증된 티커 심볼 (대문자, 영숫자/하이픈/점만 허용)
     */
    private void triggerPythonOnDemand(String ticker) throws IOException, InterruptedException {
        triggerPythonOnDemand(ticker, false);
    }

    /**
     * ProcessBuilder로 Python calculate_on_demand(ticker, force)를 실행한다.
     *
     * @param ticker 유효성이 검증된 티커 심볼 (대문자, 영숫자/하이픈/점만 허용)
     * @param force 캐시 무시 여부
     */
    private void triggerPythonOnDemand(String ticker, boolean force) throws IOException, InterruptedException {
        // 티커 유효성 검사 — 영숫자·하이픈·점만 허용 (코드 주입 방지)
        if (!ticker.matches("[A-Z0-9\\-\\.]+")) {
            throw new IllegalArgumentException("유효하지 않은 티커 형식: " + ticker);
        }

        // 프로젝트 루트 탐색 (data/ 디렉토리가 있는 경로)
        File cwd = new File("").getAbsoluteFile();
        File projectRoot;
        if (new File(cwd, "data").isDirectory()) {
            projectRoot = cwd;                           // 프로젝트 루트에서 실행 중
        } else if (cwd.getParentFile() != null
                && new File(cwd.getParentFile(), "data").isDirectory()) {
            projectRoot = cwd.getParentFile();           // backend/ 에서 실행 중
        } else {
            throw new IOException(
                    "프로젝트 루트(data/ 포함)를 찾을 수 없습니다. 현재 경로: " + cwd
            );
        }

        // Python 인라인 코드 (ticker는 이미 검증된 안전한 문자열)
        String pythonCode = String.join("\n",
                "import sys",
                "sys.path.insert(0, 'data')",
                "from scheduler.herd_scheduler import calculate_on_demand",
                "import json",
                "result = calculate_on_demand('" + ticker + "', force=" + (force ? "True" : "False") + ")",
                "print(json.dumps(result))"
        );

        ProcessBuilder pb = new ProcessBuilder(
                "data/.venv/bin/python3.12", "-c", pythonCode
        );
        pb.directory(projectRoot);
        pb.redirectErrorStream(true); // stderr → stdout 병합 (로그 수집용)

        log.info("[{}] ProcessBuilder 실행 — 루트: {}", ticker, projectRoot.getAbsolutePath());
        Process process = pb.start();

        // 출력을 별도 스레드에서 읽어 파이프 버퍼 데드락 방지
        StringBuilder outputBuf = new StringBuilder();
        Thread outputReader = new Thread(() -> {
            try {
                outputBuf.append(new String(process.getInputStream().readAllBytes()));
            } catch (IOException ignored) { }
        });
        outputReader.start();

        boolean finished = process.waitFor(30, TimeUnit.SECONDS);
        outputReader.join(2_000); // 출력 스레드 최대 2초 대기
        String output = outputBuf.toString().trim();

        if (!finished) {
            process.destroyForcibly();
            throw new IOException("[" + ticker + "] Python on-demand 타임아웃 (30초)");
        }

        if (process.exitValue() != 0) {
            throw new IOException(
                    "[" + ticker + "] Python 프로세스 종료 코드=" + process.exitValue()
                    + " / 출력: " + output
            );
        }

        log.info("[{}] Python on-demand 완료: {}", ticker, output);
    }

    /**
     * ProcessBuilder 1회로 여러 티커의 Python calculate_many_on_demand(tickers, force)를 실행한다.
     *
     * @param tickers 유효성이 검증될 티커 심볼 목록
     * @param force 캐시 무시 여부
     */
    private void triggerPythonOnDemandBatch(List<String> tickers, boolean force)
            throws IOException, InterruptedException {
        List<String> normalizedTickers = tickers.stream()
                .map(String::toUpperCase)
                .distinct()
                .toList();

        for (String ticker : normalizedTickers) {
            if (!ticker.matches("[A-Z0-9\\-\\.]+")) {
                throw new IllegalArgumentException("유효하지 않은 티커 형식: " + ticker);
            }
        }

        File cwd = new File("").getAbsoluteFile();
        File projectRoot;
        if (new File(cwd, "data").isDirectory()) {
            projectRoot = cwd;
        } else if (cwd.getParentFile() != null
                && new File(cwd.getParentFile(), "data").isDirectory()) {
            projectRoot = cwd.getParentFile();
        } else {
            throw new IOException(
                    "프로젝트 루트(data/ 포함)를 찾을 수 없습니다. 현재 경로: " + cwd
            );
        }

        String pythonTickers = normalizedTickers.stream()
                .map(t -> "'" + t + "'")
                .collect(Collectors.joining(", ", "[", "]"));

        String pythonCode = String.join("\n",
                "import sys",
                "sys.path.insert(0, 'data')",
                "from scheduler.herd_scheduler import calculate_many_on_demand",
                "import json",
                "result = calculate_many_on_demand(" + pythonTickers + ", force=" + (force ? "True" : "False") + ")",
                "print(json.dumps(result))"
        );

        ProcessBuilder pb = new ProcessBuilder(
                "data/.venv/bin/python3.12", "-c", pythonCode
        );
        pb.directory(projectRoot);
        pb.redirectErrorStream(true);

        log.info("[portfolio] ProcessBuilder 배치 실행 — tickers={}", normalizedTickers);
        Process process = pb.start();

        StringBuilder outputBuf = new StringBuilder();
        Thread outputReader = new Thread(() -> {
            try {
                outputBuf.append(new String(process.getInputStream().readAllBytes()));
            } catch (IOException ignored) { }
        });
        outputReader.start();

        boolean finished = process.waitFor(120, TimeUnit.SECONDS);
        outputReader.join(2_000);
        String output = outputBuf.toString().trim();

        if (!finished) {
            process.destroyForcibly();
            throw new IOException("[portfolio] Python on-demand 배치 타임아웃 (120초)");
        }

        if (process.exitValue() != 0) {
            throw new IOException(
                    "[portfolio] Python 배치 프로세스 종료 코드=" + process.exitValue()
                    + " / 출력: " + output
            );
        }

        failOnBatchErrors(output);

        log.info("[portfolio] Python on-demand 배치 완료: {}", output);
    }

    /**
     * Python 배치 함수는 종목별 실패를 JSON errors 배열로 반환한다.
     * 수동 새로고침 API에서는 실패를 조용히 숨기지 않고 클라이언트에 알려준다.
     */
    private void failOnBatchErrors(String output) throws IOException {
        String jsonLine = null;
        for (String line : output.split("\\R")) {
            String trimmed = line.trim();
            if (trimmed.startsWith("{") && trimmed.contains("\"errors\"")) {
                jsonLine = trimmed;
            }
        }

        if (jsonLine == null) {
            return;
        }

        JsonNode root = new ObjectMapper().readTree(jsonLine);
        JsonNode errors = root.get("errors");
        if (errors != null && errors.isArray() && !errors.isEmpty()) {
            throw new IOException("[portfolio] 일부 HERD 갱신 실패: " + errors);
        }
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
     * 특정 종목의 HERD 점수 히스토리 조회.
     * period 문자열을 파싱해 기준일을 산출하고 그 이후 데이터를 날짜 오름차순으로 반환.
     *
     * @param ticker 티커 심볼 (대문자)
     * @param period "3y" / "1y" / "6m" 등 — 미지원 형식은 기본값 3y 적용
     */
    public HerdHistoryResponse getHerdHistory(String ticker, String period) {
        LocalDate cutoff = parsePeriod(period);
        List<HerdScore> scores = herdScoreRepository.findHistoryByTickerSince(ticker, cutoff);
        List<HerdHistoryPoint> points = scores.stream()
                .map(s -> HerdHistoryPoint.builder()
                        .date(s.getScoreDate().toString())
                        .score(s.getHerdScore().doubleValue())
                        .build())
                .toList();
        return HerdHistoryResponse.builder().points(points).build();
    }

    /** "3y" → today-3년, "1y" → today-1년, "6m" → today-6개월, 그 외 기본 3년 */
    private LocalDate parsePeriod(String period) {
        if (period == null || period.isBlank()) return LocalDate.now().minusYears(3);
        try {
            if (period.endsWith("y")) {
                return LocalDate.now().minusYears(Long.parseLong(period.replace("y", "")));
            }
            if (period.endsWith("m")) {
                return LocalDate.now().minusMonths(Long.parseLong(period.replace("m", "")));
            }
        } catch (NumberFormatException ignored) { }
        return LocalDate.now().minusYears(3);
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

        return buildResponse(score.get(), indicator);
    }

    /** HERD 점수 응답에 데이터 신뢰도 레이어를 붙인다. */
    private HerdScoreResponse buildResponse(HerdScore score, HerdIndicator indicator) {
        HerdQuality quality = calculateQuality(score, indicator);
        return HerdScoreResponse.of(
                score,
                indicator,
                quality.score(),
                quality.level(),
                quality.label(),
                quality.summary(),
                quality.flags(),
                quality.reasons()
        );
    }

    /**
     * HERD 신뢰도 계산.
     * 핵심 지표 완성도, 200주 MA 포함 여부, v4 보정 승수 상태, 최신성을 종합해
     * 사용자가 HERD 점수를 얼마나 강하게 반영해도 되는지 보여준다.
     *
     * 주의: daily_prices는 운영 화면용 최신 가격 저장에 가깝고, Python 계산에 사용된
     * 전체 히스토리 길이를 완전히 대표하지 않는다. 따라서 신뢰도는 저장된 산출 결과의
     * 완성도를 기준으로 계산한다.
     */
    private HerdQuality calculateQuality(HerdScore score, HerdIndicator indicator) {
        List<String> flags = new ArrayList<>();
        List<String> reasons = new ArrayList<>();
        int qualityScore = 0;

        int activeIndicatorCount = countPresentIndicators(indicator);
        qualityScore += activeIndicatorCount * 9; // 활성 핵심 지표 5개 × 9점 = 45점
        if (activeIndicatorCount == 5) {
            flags.add("CORE_INDICATORS_COMPLETE");
            reasons.add("핵심 지표 5개 모두 계산됨");
        } else {
            flags.add("CORE_INDICATORS_PARTIAL");
            reasons.add("핵심 지표 " + activeIndicatorCount + "/5개 계산됨");
        }

        if (indicator != null && indicator.getMa200Weekly() != null) {
            qualityScore += 20;
            flags.add("MA200_WEEKLY_AVAILABLE");
            reasons.add("200주 MA 위치 지표 포함");
        } else {
            flags.add("MA200_WEEKLY_MISSING");
            reasons.add("200주 MA 위치 데이터 없음");
        }

        BigDecimal epsMultiplier = indicator != null ? indicator.getEpsMultiplier() : null;
        if (isNonNeutralMultiplier(epsMultiplier)) {
            qualityScore += 10;
            flags.add("EPS_MULTIPLIER_APPLIED");
            reasons.add("EPS 서프라이즈 보정 적용");
        } else if (epsMultiplier != null) {
            qualityScore += 8;
            flags.add("EPS_MULTIPLIER_NEUTRAL");
            reasons.add("EPS 보정은 중립값");
        } else {
            flags.add("EPS_MULTIPLIER_MISSING");
            reasons.add("EPS 보정 데이터 없음");
        }

        BigDecimal sectorMultiplier = indicator != null ? indicator.getSectorMultiplier() : null;
        if (isNonNeutralMultiplier(sectorMultiplier)) {
            qualityScore += 10;
            flags.add("SECTOR_MULTIPLIER_APPLIED");
            reasons.add("섹터 상대 강도 보정 적용");
        } else if (sectorMultiplier != null) {
            qualityScore += 8;
            flags.add("SECTOR_MULTIPLIER_NEUTRAL");
            reasons.add("섹터 강도 보정은 중립값");
        } else {
            flags.add("SECTOR_MULTIPLIER_MISSING");
            reasons.add("섹터 강도 보정 데이터 없음");
        }

        long scoreAgeDays = ChronoUnit.DAYS.between(score.getScoreDate(), LocalDate.now());
        if (scoreAgeDays > 14) {
            flags.add("SCORE_STALE");
            reasons.add("HERD 점수가 14일 이상 갱신되지 않음");
        } else if (scoreAgeDays > 7) {
            qualityScore += 8;
            flags.add("SCORE_AGING");
            reasons.add("HERD 점수가 7일 이상 갱신되지 않음");
        } else {
            qualityScore += 15;
            flags.add("SCORE_FRESH");
            reasons.add("최근 7일 이내 HERD 점수");
        }

        qualityScore = Math.max(0, Math.min(100, qualityScore));
        String level = qualityLevel(qualityScore);
        String label = qualityLabel(level);
        String summary = qualitySummary(level, activeIndicatorCount, flags);

        return new HerdQuality(qualityScore, level, label, summary, flags, reasons);
    }

    private int countPresentIndicators(HerdIndicator indicator) {
        if (indicator == null) {
            return 0;
        }
        int count = 0;
        if (indicator.getMonthlyRsi() != null) count++;
        if (indicator.getWeeklyRsi() != null) count++;
        if (indicator.getPosition52w() != null) count++;
        if (indicator.getMa200Deviation() != null) count++;
        if (indicator.getMa200Weekly() != null) count++;
        return count;
    }

    private boolean isNonNeutralMultiplier(BigDecimal value) {
        return value != null && value.compareTo(BigDecimal.ONE) != 0;
    }

    private String qualityLevel(int score) {
        if (score >= 85) return "HIGH";
        if (score >= 65) return "GOOD";
        if (score >= 45) return "LIMITED";
        return "LOW";
    }

    private String qualityLabel(String level) {
        return switch (level) {
            case "HIGH" -> "신뢰도 높음";
            case "GOOD" -> "신뢰도 보통";
            case "LIMITED" -> "제한적";
            default -> "참고용";
        };
    }

    private String qualitySummary(
            String level,
            int activeIndicatorCount,
            List<String> flags
    ) {
        if ("HIGH".equals(level)) {
            return "핵심 지표와 보정 데이터가 충분해 HERD 판단을 강하게 참고할 수 있습니다.";
        }
        if ("GOOD".equals(level)) {
            return "핵심 지표는 충분하지만 일부 보정은 중립 또는 제한적으로 반영됩니다.";
        }
        if ("LIMITED".equals(level)) {
            if (flags.contains("MA200_WEEKLY_MISSING")) {
                return "장기 추세 지표 일부가 부족해 HERD 판단은 보조 신호로 보는 편이 좋습니다.";
            }
            return "일부 핵심 지표가 부족해 HERD 판단은 보조 신호로 보는 편이 좋습니다.";
        }
        if (activeIndicatorCount < 3) {
            return "데이터가 부족해 현재 HERD 점수는 참고용으로만 활용하는 것이 좋습니다.";
        }
        return "신뢰도 낮음 구간으로, 포지션 크기를 작게 두고 추가 확인이 필요합니다.";
    }

    /** HERD 신뢰도 계산 결과 */
    private record HerdQuality(
            int score,
            String level,
            String label,
            String summary,
            List<String> flags,
            List<String> reasons
    ) {
    }
}
