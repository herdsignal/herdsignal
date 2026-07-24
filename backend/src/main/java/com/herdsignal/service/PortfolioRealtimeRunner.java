package com.herdsignal.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Python 스케줄러의 실시간 포트폴리오 계산을 실행하는 인프라 어댑터.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PortfolioRealtimeRunner {

    private static final long PROCESS_TIMEOUT_SECONDS = 30;
    private static final long READER_JOIN_MILLIS = 5_000;

    private final ObjectMapper objectMapper;

    public Map<String, Object> calculate(String userId) {
        validateUserId(userId);
        try {
            Path projectRoot = Paths.get(System.getProperty("user.dir")).getParent();
            Path pythonExecutable = projectRoot.resolve("data/.venv/bin/python3.12");
            String script = pythonScript(userId);
            ProcessBuilder processBuilder =
                    new ProcessBuilder(pythonExecutable.toString(), "-c", script);
            processBuilder.directory(projectRoot.toFile());
            return execute(processBuilder);
        } catch (RuntimeException exception) {
            throw exception;
        } catch (Exception exception) {
            log.error("[realtime] Python 스크립트 실행 실패: {}", exception.getMessage(), exception);
            throw new RuntimeException("실시간 포트폴리오 계산 실패: " + exception.getMessage());
        }
    }

    private Map<String, Object> execute(ProcessBuilder processBuilder) throws Exception {
        Process process = processBuilder.start();
        StringBuilder output = new StringBuilder();
        StringBuilder error = new StringBuilder();
        Thread stdoutReader = streamReader(process.getInputStream(), output, "stdout");
        Thread stderrReader = streamReader(process.getErrorStream(), error, "stderr");
        stdoutReader.start();
        stderrReader.start();

        boolean finished = process.waitFor(PROCESS_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        if (!finished) {
            process.destroyForcibly();
        }
        stdoutReader.join(READER_JOIN_MILLIS);
        stderrReader.join(READER_JOIN_MILLIS);

        if (!finished) {
            throw new RuntimeException("Python 스크립트 30초 타임아웃");
        }
        assertSuccessful(process.exitValue(), output, error);
        return objectMapper.readValue(output.toString().trim(), new TypeReference<>() { });
    }

    private Thread streamReader(
            java.io.InputStream stream,
            StringBuilder destination,
            String streamName
    ) {
        return new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    destination.append(line).append('\n');
                }
            } catch (IOException exception) {
                log.warn("[realtime] {} 읽기 오류: {}", streamName, exception.getMessage());
            }
        }, "portfolio-realtime-" + streamName);
    }

    private void assertSuccessful(int exitCode, StringBuilder output, StringBuilder error) {
        String errorText = error.toString().trim();
        if (exitCode != 0) {
            log.error("[realtime] Python 스크립트 실패 (exit={}):\n{}", exitCode, errorText);
            throw new RuntimeException(
                    "Python 스크립트 실패 (exit=" + exitCode + "):\n" + errorText);
        }
        if (!errorText.isEmpty()) {
            log.debug("[realtime] Python 로그:\n{}", errorText);
        }
        if (output.toString().isBlank()) {
            throw new RuntimeException("Python 스크립트 출력 없음 (exit=" + exitCode + ")");
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
