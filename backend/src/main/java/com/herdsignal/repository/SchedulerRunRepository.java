package com.herdsignal.repository;

import com.herdsignal.domain.SchedulerRun;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface SchedulerRunRepository extends JpaRepository<SchedulerRun, Long> {
    Optional<SchedulerRun> findTopByJobNameOrderByStartedAtDesc(String jobName);
}
