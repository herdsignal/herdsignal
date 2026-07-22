package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Pattern;

/** Python 데이터 엔진의 on-demand HERD 계산을 격리해 실행한다. */
@Slf4j
@Component
public class HerdOnDemandRunner {
    private static final Pattern SAFE_TICKER = Pattern.compile("[A-Z0-9.-]+");
    private static final int SINGLE_TIMEOUT_SECONDS = 30;
    private static final int BATCH_TIMEOUT_SECONDS = 120;

    private final ObjectMapper objectMapper;
    private final String configuredPythonExecutable;

    public HerdOnDemandRunner(
            ObjectMapper objectMapper,
            @Value("${herdsignal.python.executable:}") String configuredPythonExecutable
    ) {
        this.objectMapper = objectMapper;
        this.configuredPythonExecutable = configuredPythonExecutable == null
                ? ""
                : configuredPythonExecutable.trim();
    }

    public void refresh(String ticker, boolean force) throws IOException, InterruptedException {
        String normalizedTicker = normalizeTickers(List.of(ticker)).get(0);
        String pythonTicker = objectMapper.writeValueAsString(normalizedTicker);
        String code = String.join("\n",
                "import json, sys",
                "sys.path.insert(0, 'data')",
                "from scheduler.herd_scheduler import calculate_on_demand",
                "result = calculate_on_demand(" + pythonTicker + ", force=" + pythonBoolean(force) + ")",
                "print(json.dumps(result))"
        );
        String output = execute("[" + normalizedTicker + "]", code, SINGLE_TIMEOUT_SECONDS);
        log.info("[{}] Python on-demand 완료: {}", normalizedTicker, output);
    }

    public void refreshMany(List<String> tickers, boolean force) throws IOException, InterruptedException {
        List<String> normalizedTickers = normalizeTickers(tickers);
        if (normalizedTickers.isEmpty()) {
            return;
        }
        String pythonTickers = objectMapper.writeValueAsString(normalizedTickers);
        String code = String.join("\n",
                "import json, sys",
                "sys.path.insert(0, 'data')",
                "from scheduler.herd_scheduler import calculate_many_on_demand",
                "result = calculate_many_on_demand(" + pythonTickers + ", force=" + pythonBoolean(force) + ")",
                "print(json.dumps(result))"
        );
        String output = execute("[portfolio]", code, BATCH_TIMEOUT_SECONDS);
        failOnBatchErrors(output);
        log.info("[portfolio] Python on-demand 배치 완료: {}", output);
    }

    List<String> normalizeTickers(List<String> tickers) {
        if (tickers == null) {
            throw new IllegalArgumentException("티커 목록이 필요합니다.");
        }
        return tickers.stream()
                .map(ticker -> {
                    if (ticker == null || ticker.isBlank()) {
                        throw new IllegalArgumentException("빈 티커는 허용되지 않습니다.");
                    }
                    String normalized = ticker.trim().toUpperCase(Locale.ROOT);
                    if (!SAFE_TICKER.matcher(normalized).matches()) {
                        throw new IllegalArgumentException("유효하지 않은 티커 형식: " + ticker);
                    }
                    return normalized;
                })
                .distinct()
                .toList();
    }

    void failOnBatchErrors(String output) throws IOException {
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
        JsonNode errors = objectMapper.readTree(jsonLine).path("errors");
        if (errors.isArray() && !errors.isEmpty()) {
            throw new IOException("[portfolio] 일부 HERD 갱신 실패: " + errors);
        }
    }

    private String execute(String label, String code, int timeoutSeconds)
            throws IOException, InterruptedException {
        Path projectRoot = findProjectRoot(Path.of("").toAbsolutePath());
        ProcessBuilder processBuilder = new ProcessBuilder(
                resolvePythonExecutable(projectRoot), "-c", code
        );
        processBuilder.directory(projectRoot.toFile());
        processBuilder.redirectErrorStream(true);

        log.info("{} Python 실행 — root={}", label, projectRoot);
        Process process = processBuilder.start();
        StringBuilder output = new StringBuilder();
        AtomicReference<IOException> readFailure = new AtomicReference<>();
        Thread outputReader = new Thread(() -> {
            try {
                output.append(new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8));
            } catch (IOException exception) {
                readFailure.set(exception);
            }
        }, "herd-python-output");
        outputReader.setDaemon(true);
        outputReader.start();

        try {
            if (!process.waitFor(timeoutSeconds, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                process.waitFor(2, TimeUnit.SECONDS);
                throw new IOException(label + " Python on-demand 타임아웃 (" + timeoutSeconds + "초)");
            }
            outputReader.join(2_000);
        } catch (InterruptedException exception) {
            process.destroyForcibly();
            Thread.currentThread().interrupt();
            throw exception;
        }

        if (readFailure.get() != null) {
            throw new IOException(label + " Python 출력 읽기 실패", readFailure.get());
        }
        String result = output.toString().trim();
        if (process.exitValue() != 0) {
            throw new IOException(label + " Python 프로세스 종료 코드="
                    + process.exitValue() + " / 출력: " + result);
        }
        return result;
    }

    Path findProjectRoot(Path currentDirectory) throws IOException {
        Path current = currentDirectory.normalize();
        if (Files.isDirectory(current.resolve("data"))) {
            return current;
        }
        Path parent = current.getParent();
        if (parent != null && Files.isDirectory(parent.resolve("data"))) {
            return parent;
        }
        throw new IOException("프로젝트 루트(data/ 포함)를 찾을 수 없습니다: " + current);
    }

    String resolvePythonExecutable(Path projectRoot) throws IOException {
        if (!configuredPythonExecutable.isBlank()) {
            return configuredPythonExecutable;
        }
        for (String candidate : List.of("python", "python3", "python3.12")) {
            Path executable = projectRoot.resolve("data/.venv/bin").resolve(candidate);
            if (Files.isExecutable(executable)) {
                return executable.toString();
            }
        }
        throw new IOException("data/.venv Python 실행 파일을 찾을 수 없습니다. "
                + "HERD_PYTHON_EXECUTABLE을 설정하세요.");
    }

    private String pythonBoolean(boolean value) {
        return value ? "True" : "False";
    }
}
