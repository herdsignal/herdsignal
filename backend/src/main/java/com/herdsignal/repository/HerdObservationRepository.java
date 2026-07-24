package com.herdsignal.repository;

import com.herdsignal.domain.HerdObservation;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/** HERD S1 관찰 스냅샷 조회 전용 저장소. */
public interface HerdObservationRepository
        extends JpaRepository<HerdObservation, Long> {

    Optional<HerdObservation>
    findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
            String ticker,
            String stateModelVersion
    );

    List<HerdObservation>
    findByTickerAndStateModelVersionOrderByObservationDateDesc(
            String ticker,
            String stateModelVersion,
            Pageable pageable
    );
}
