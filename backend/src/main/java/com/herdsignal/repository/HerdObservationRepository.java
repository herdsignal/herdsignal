package com.herdsignal.repository;

import com.herdsignal.domain.HerdObservation;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.time.LocalDate;
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

    @Query("""
            select observation
            from HerdObservation observation
            where observation.stateModelVersion = :stateModelVersion
              and observation.ticker in :tickers
              and observation.observationDate = (
                  select max(candidate.observationDate)
                  from HerdObservation candidate
                  where candidate.ticker = observation.ticker
                    and candidate.stateModelVersion = :stateModelVersion
              )
            """)
    List<HerdObservation> findLatestByTickersAndStateModelVersion(
            @Param("tickers") List<String> tickers,
            @Param("stateModelVersion") String stateModelVersion
    );

    @Query("""
            select observation
            from HerdObservation observation
            where observation.stateModelVersion = :stateModelVersion
              and observation.ticker in :tickers
              and observation.observationDate >= :fromDate
            order by observation.observationDate desc, observation.ticker asc
            """)
    List<HerdObservation> findTrackedHistorySince(
            @Param("tickers") List<String> tickers,
            @Param("stateModelVersion") String stateModelVersion,
            @Param("fromDate") LocalDate fromDate
    );
}
