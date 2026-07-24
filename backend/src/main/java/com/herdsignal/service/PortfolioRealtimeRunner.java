package com.herdsignal.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;

/**
 * Python 스케줄러의 실시간 포트폴리오 계산을 실행하는 인프라 어댑터.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PortfolioRealtimeRunner {

    private final ObjectMapper objectMapper;
    private final PythonProcessGateway processGateway;

    public Map<String, Object> calculate(String userId) {
        validateUserId(userId);
        try {
            String script = pythonScript(userId);
            String output = processGateway.executeInline(
                    "[portfolio-realtime]",
                    script,
                    Duration.ofSeconds(30)
            ).stdout();
            return objectMapper.readValue(output, new TypeReference<>() {});
        } catch (RuntimeException exception) {
            throw exception;
        } catch (Exception exception) {
            log.error("[realtime] Python 스크립트 실행 실패: {}", exception.getMessage(), exception);
            throw new RuntimeException("실시간 포트폴리오 계산 실패: " + exception.getMessage());
        }
    }

    private String pythonScript(String userId) throws IOException {
        String userIdLiteral = objectMapper.writeValueAsString(userId);
        return String.join("\n",
                "import sys, json",
                "sys.path.insert(0, 'data')",
                "from scheduler.herd_scheduler import calculate_current_portfolio",
                "print(json.dumps(calculate_current_portfolio(" + userIdLiteral + ")))"
        );
    }

    private void validateUserId(String userId) {
        if (userId == null || !userId.matches("[A-Za-z0-9_-]{1,50}")) {
            throw new IllegalArgumentException("유효하지 않은 사용자 ID입니다.");
        }
    }
}
