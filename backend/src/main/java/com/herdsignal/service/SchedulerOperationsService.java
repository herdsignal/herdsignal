package com.herdsignal.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.atomic.AtomicBoolean;

@Service
@Slf4j
public class SchedulerOperationsService {
    private static final Duration MANUAL_RUN_TIMEOUT = Duration.ofHours(2);

    private final PythonProcessGateway processGateway;
    private final Executor schedulerOperationsExecutor;
    private final AtomicBoolean requested = new AtomicBoolean(false);

    public SchedulerOperationsService(
            PythonProcessGateway processGateway,
            @Qualifier("schedulerOperationsExecutor") Executor schedulerOperationsExecutor
    ) {
        this.processGateway = processGateway;
        this.schedulerOperationsExecutor = schedulerOperationsExecutor;
    }

    public boolean requestManualRun() {
        if (!requested.compareAndSet(false, true)) return false;
        try {
            schedulerOperationsExecutor.execute(this::runManualUpdate);
            return true;
        } catch (RejectedExecutionException exception) {
            requested.set(false);
            return false;
        }
    }

    public boolean requestDailyRun() {
        if (!requested.compareAndSet(false, true)) return false;
        try {
            schedulerOperationsExecutor.execute(this::runDailyUpdate);
            return true;
        } catch (RejectedExecutionException exception) {
            requested.set(false);
            return false;
        }
    }

    private void runManualUpdate() {
        try {
            processGateway.executeScript(
                    "Tier1 수동 갱신",
                    "data/scheduler/herd_scheduler.py",
                    List.of("--run-now"),
                    MANUAL_RUN_TIMEOUT
            );
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log.warn("Tier1 수동 갱신 대기가 중단됐습니다.", exception);
        } catch (Exception exception) {
            log.error("Tier1 수동 갱신 실행에 실패했습니다.", exception);
        } finally {
            requested.set(false);
        }
    }

    private void runDailyUpdate() {
        try {
            processGateway.executeScript(
                    "Daily D1 수동 갱신",
                    "data/scheduler/herd_scheduler.py",
                    List.of("--daily-now"),
                    MANUAL_RUN_TIMEOUT
            );
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log.warn("Daily D1 수동 갱신 대기가 중단됐습니다.", exception);
        } catch (Exception exception) {
            log.error("Daily D1 수동 갱신 실행에 실패했습니다.", exception);
        } finally {
            requested.set(false);
        }
    }
}
