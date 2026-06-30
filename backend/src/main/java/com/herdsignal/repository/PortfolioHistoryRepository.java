package com.herdsignal.repository;

import com.herdsignal.domain.PortfolioHistory;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * portfolio_history 테이블 읽기 전용 접근 인터페이스.
 * Python 스케줄러가 매일 저장한 포트폴리오 스냅샷을 조회.
 */
public interface PortfolioHistoryRepository extends JpaRepository<PortfolioHistory, Long> {

    /**
     * 특정 사용자의 최신 1개 스냅샷 조회.
     * 포트폴리오 요약(총 평가금액, 수익률) 조회에 사용.
     */
    Optional<PortfolioHistory> findTopByUserIdOrderBySnapshotDateDesc(String userId);

    /**
     * 특정 사용자의 최신 2개 스냅샷 조회.
     * 일일 등락률 계산 (오늘 vs 전일 total_value 비교)에 사용.
     */
    List<PortfolioHistory> findTop2ByUserIdOrderBySnapshotDateDesc(String userId);

    /**
     * 특정 사용자의 날짜 범위 내 스냅샷 전체 조회 (오래된 순).
     * 포트폴리오 히스토리 차트 데이터 제공에 사용.
     * period=month → 최근 30일 / period=year → 최근 365일
     */
    List<PortfolioHistory> findByUserIdAndSnapshotDateBetweenOrderBySnapshotDateAsc(
            String userId, LocalDate start, LocalDate end);

    /**
     * 특정 사용자의 전체 스냅샷 조회 (최신 순).
     * 전체 히스토리 조회에 사용.
     */
    List<PortfolioHistory> findByUserIdOrderBySnapshotDateDesc(String userId);
}
