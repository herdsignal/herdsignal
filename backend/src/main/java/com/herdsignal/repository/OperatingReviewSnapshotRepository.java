package com.herdsignal.repository;

import com.herdsignal.domain.OperatingReviewSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface OperatingReviewSnapshotRepository extends JpaRepository<OperatingReviewSnapshot, Long> {
    List<OperatingReviewSnapshot> findByUserIdAndTickerOrderByReviewedAtDesc(String userId, String ticker);
}
