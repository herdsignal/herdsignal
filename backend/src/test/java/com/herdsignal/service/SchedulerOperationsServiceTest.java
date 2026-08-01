package com.herdsignal.service;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.RejectedExecutionException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class SchedulerOperationsServiceTest {

    @Test
    void acceptsRequestAndRunsTier1ManualCommand() throws Exception {
        PythonProcessGateway gateway = mock(PythonProcessGateway.class);
        SchedulerOperationsService service =
                new SchedulerOperationsService(gateway, Runnable::run);

        assertThat(service.requestManualRun()).isTrue();

        verify(gateway).executeScript(
                "Tier1 수동 갱신",
                "data/scheduler/herd_scheduler.py",
                List.of("--run-now"),
                Duration.ofHours(2)
        );
    }

    @Test
    void acceptsDailyRequestAndRunsLightweightCommand() throws Exception {
        PythonProcessGateway gateway = mock(PythonProcessGateway.class);
        SchedulerOperationsService service =
                new SchedulerOperationsService(gateway, Runnable::run);

        assertThat(service.requestDailyRun()).isTrue();

        verify(gateway).executeScript(
                "Daily D1 수동 갱신",
                "data/scheduler/herd_scheduler.py",
                List.of("--daily-now"),
                Duration.ofHours(2)
        );
    }

    @Test
    void releasesRequestFlagWhenExecutorRejectsTask() {
        PythonProcessGateway gateway = mock(PythonProcessGateway.class);
        Executor rejectingExecutor = command -> {
            throw new RejectedExecutionException();
        };
        SchedulerOperationsService service =
                new SchedulerOperationsService(gateway, rejectingExecutor);

        assertThat(service.requestManualRun()).isFalse();
        assertThat(service.requestManualRun()).isFalse();
    }
}
