package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

class SchedulerHeartbeatServiceTest {
    private static final Clock CLOCK = Clock.fixed(
            Instant.parse("2026-08-01T12:03:00Z"), ZoneOffset.UTC);

    @TempDir
    Path tempDir;

    @Test
    void acceptsOnlyRecentRunningHeartbeat() throws Exception {
        Path path = tempDir.resolve("heartbeat.json");
        Files.writeString(path, """
                {
                  "schemaVersion": "HERD_SCHEDULER_HEARTBEAT_V1",
                  "status": "RUNNING",
                  "lastHeartbeatAt": "2026-08-01T12:02:00+00:00"
                }
                """);

        SchedulerHeartbeatService.Status status = service(path).getStatus();

        assertThat(status.status()).isEqualTo("RUNNING");
        assertThat(status.running()).isTrue();
        assertThat(status.ageSeconds()).isEqualTo(60);
    }

    @Test
    void marksOldOrMissingHeartbeatUnavailableForAutomation() throws Exception {
        Path stale = tempDir.resolve("stale.json");
        Files.writeString(stale, """
                {
                  "schemaVersion": "HERD_SCHEDULER_HEARTBEAT_V1",
                  "status": "RUNNING",
                  "lastHeartbeatAt": "2026-08-01T11:50:00+00:00"
                }
                """);

        assertThat(service(stale).getStatus().status()).isEqualTo("STALE");
        assertThat(service(stale).getStatus().running()).isFalse();
        assertThat(service(tempDir.resolve("missing.json")).getStatus().status())
                .isEqualTo("UNAVAILABLE");
    }

    private SchedulerHeartbeatService service(Path path) {
        return new SchedulerHeartbeatService(
                new ObjectMapper(), path.toString(), CLOCK);
    }
}
