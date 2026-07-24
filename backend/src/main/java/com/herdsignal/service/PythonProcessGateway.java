package com.herdsignal.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Python 프로세스 실행 정책을 한곳에 모은 인프라 경계. */
@Component
public class PythonProcessGateway {
    private static final int MAX_CONCURRENT_PROCESSES = 2;
    private static final int MAX_OUTPUT_BYTES = 2 * 1024 * 1024;
    private static final long READER_JOIN_MILLIS = 5_000;

    private final String configuredPythonExecutable;
    private final Semaphore permits = new Semaphore(MAX_CONCURRENT_PROCESSES);

    public PythonProcessGateway(
            @Value("${herdsignal.python.executable:}") String configuredPythonExecutable
    ) {
        this.configuredPythonExecutable = configuredPythonExecutable == null
                ? ""
                : configuredPythonExecutable.trim();
    }

    public Result executeInline(String label, String code, Duration timeout)
            throws IOException, InterruptedException {
        return execute(label, List.of("-c", code), timeout);
    }

    public Result executeScript(
            String label,
            String projectRelativeScript,
            List<String> arguments,
            Duration timeout
    ) throws IOException, InterruptedException {
        List<String> commandArguments = new ArrayList<>();
        commandArguments.add(projectRelativeScript);
        commandArguments.addAll(arguments);
        return execute(label, commandArguments, timeout);
    }

    Result execute(String label, List<String> arguments, Duration timeout)
            throws IOException, InterruptedException {
        if (!permits.tryAcquire(1, TimeUnit.SECONDS)) {
            throw new IOException(label + " Python 실행 대기열이 가득 찼습니다.");
        }
        try {
            Path projectRoot = findProjectRoot(Path.of("").toAbsolutePath());
            List<String> command = new ArrayList<>();
            command.add(resolvePythonExecutable(projectRoot));
            command.addAll(arguments);
            ProcessBuilder builder = new ProcessBuilder(command);
            builder.directory(projectRoot.toFile());
            return run(label, builder, timeout);
        } finally {
            permits.release();
        }
    }

    private Result run(String label, ProcessBuilder builder, Duration timeout)
            throws IOException, InterruptedException {
        Process process = builder.start();
        StreamCapture stdout = new StreamCapture(process.getInputStream());
        StreamCapture stderr = new StreamCapture(process.getErrorStream());
        Thread stdoutThread = new Thread(stdout, "python-stdout");
        Thread stderrThread = new Thread(stderr, "python-stderr");
        stdoutThread.setDaemon(true);
        stderrThread.setDaemon(true);
        stdoutThread.start();
        stderrThread.start();

        try {
            if (!process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS)) {
                process.destroyForcibly();
                process.waitFor(2, TimeUnit.SECONDS);
                throw new IOException(label + " Python 실행 타임아웃 (" + timeout.toSeconds() + "초)");
            }
            stdoutThread.join(READER_JOIN_MILLIS);
            stderrThread.join(READER_JOIN_MILLIS);
        } catch (InterruptedException exception) {
            process.destroyForcibly();
            Thread.currentThread().interrupt();
            throw exception;
        }

        stdout.assertReadable(label, "stdout");
        stderr.assertReadable(label, "stderr");
        Result result = new Result(stdout.text(), stderr.text(), process.exitValue());
        if (result.exitCode() != 0) {
            throw new IOException(label + " Python 종료 코드=" + result.exitCode()
                    + " / stderr: " + result.stderr());
        }
        if (result.stdout().isBlank()) {
            throw new IOException(label + " Python 출력이 없습니다.");
        }
        return result;
    }

    Path findProjectRoot(Path currentDirectory) throws IOException {
        Path current = currentDirectory.normalize();
        if (Files.isDirectory(current.resolve("data"))) return current;
        Path parent = current.getParent();
        if (parent != null && Files.isDirectory(parent.resolve("data"))) return parent;
        throw new IOException("프로젝트 루트(data/ 포함)를 찾을 수 없습니다: " + current);
    }

    String resolvePythonExecutable(Path projectRoot) throws IOException {
        if (!configuredPythonExecutable.isBlank()) return configuredPythonExecutable;
        for (String candidate : List.of("python", "python3", "python3.12")) {
            Path executable = projectRoot.resolve("data/.venv/bin").resolve(candidate);
            if (Files.isExecutable(executable)) return executable.toString();
        }
        throw new IOException("data/.venv Python 실행 파일을 찾을 수 없습니다. "
                + "HERD_PYTHON_EXECUTABLE을 설정하세요.");
    }

    public record Result(String stdout, String stderr, int exitCode) {}

    private static final class StreamCapture implements Runnable {
        private final InputStream stream;
        private final ByteArrayOutputStream captured = new ByteArrayOutputStream();
        private final AtomicReference<IOException> failure = new AtomicReference<>();
        private boolean truncated;

        private StreamCapture(InputStream stream) {
            this.stream = stream;
        }

        @Override
        public void run() {
            byte[] buffer = new byte[8_192];
            try (stream) {
                int count;
                while ((count = stream.read(buffer)) >= 0) {
                    int remaining = MAX_OUTPUT_BYTES - captured.size();
                    if (remaining > 0) {
                        captured.write(buffer, 0, Math.min(count, remaining));
                    }
                    if (count > remaining) truncated = true;
                }
            } catch (IOException exception) {
                failure.set(exception);
            }
        }

        private void assertReadable(String label, String streamName) throws IOException {
            if (failure.get() != null) {
                throw new IOException(label + " " + streamName + " 읽기 실패", failure.get());
            }
            if (truncated) {
                throw new IOException(label + " " + streamName + " 출력이 2MB를 초과했습니다.");
            }
        }

        private String text() {
            return captured.toString(StandardCharsets.UTF_8).trim();
        }
    }
}
