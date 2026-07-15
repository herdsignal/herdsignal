package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(name = "scheduler_runs")
@Getter
@NoArgsConstructor
public class SchedulerRun {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "job_name", nullable = false, length = 50)
    private String jobName;

    @Column(name = "trigger_type", nullable = false, length = 20)
    private String triggerType;

    @Column(nullable = false, length = 30)
    private String status;

    @Column(name = "started_at", nullable = false)
    private LocalDateTime startedAt;

    @Column(name = "finished_at")
    private LocalDateTime finishedAt;

    @Column(name = "total_count", nullable = false)
    private Integer totalCount;

    @Column(name = "success_count", nullable = false)
    private Integer successCount;

    @Column(name = "failed_count", nullable = false)
    private Integer failedCount;

    @Column(name = "failed_tickers", columnDefinition = "TEXT")
    private String failedTickers;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;
}
