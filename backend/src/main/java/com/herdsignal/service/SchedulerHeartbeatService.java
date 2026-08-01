package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.time.OffsetDateTime;

/** Python 스케줄러의 최근 heartbeat를 fail-closed 방식으로 판정한다. */
@Service
public class SchedulerHeartbeatService {
    static final String SCHEMA = "HERD_SCHEDULER_HEARTBEAT_V1";
    static final long MAX_HEARTBEAT_AGE_SECONDS = 180;

    private final ObjectMapper objectMapper;
    private final Path heartbeatPath;
    private final Clock clock;

    @Autowired
    public SchedulerHeartbeatService(
            ObjectMapper objectMapper,
            @Value("${herdsignal.scheduler.heartbeat-path:"
                    + "../runtime/scheduler-heartbeat.json}")
            String heartbeatPath
    ) {
        this(objectMapper, heartbeatPath, Clock.systemUTC());
    }

    SchedulerHeartbeatService(ObjectMapper objectMapper, String heartbeatPath, Clock clock) {
        this.objectMapper = objectMapper;
        this.heartbeatPath = Path.of(heartbeatPath).toAbsolutePath().normalize();
        this.clock = clock;
    }

    public Status getStatus() {
        if (!Files.isRegularFile(heartbeatPath)) {
            return unavailable("UNAVAILABLE");
        }
        try {
            JsonNode root = objectMapper.readTree(Files.readAllBytes(heartbeatPath));
            if (!SCHEMA.equals(root.path("schemaVersion").asText())) {
                return unavailable("INVALID");
            }
            OffsetDateTime lastHeartbeatAt = OffsetDateTime.parse(
                    root.path("lastHeartbeatAt").asText());
            long ageSeconds = Math.max(0, Duration.between(
                    lastHeartbeatAt.toInstant(), clock.instant()).getSeconds());
            String reportedStatus = root.path("status").asText("UNKNOWN");
            boolean running = "RUNNING".equals(reportedStatus)
                    && ageSeconds <= MAX_HEARTBEAT_AGE_SECONDS;
            String status = running
                    ? "RUNNING"
                    : "STOPPED".equals(reportedStatus) ? "STOPPED" : "STALE";
            return new Status(status, running, lastHeartbeatAt, ageSeconds);
        } catch (IOException | RuntimeException exception) {
            return unavailable("INVALID");
        }
    }

    private Status unavailable(String status) {
        return new Status(status, false, null, null);
    }

    public record Status(
            String status,
            boolean running,
            OffsetDateTime lastHeartbeatAt,
            Long ageSeconds
    ) {}
}
