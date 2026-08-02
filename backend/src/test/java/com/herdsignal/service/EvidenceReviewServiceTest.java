package com.herdsignal.service;

import com.herdsignal.dto.EvidenceReviewResponse;
import com.herdsignal.dto.HerdObservationResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class EvidenceReviewServiceTest {
    private HerdObservationService observationService;
    private EvidenceReviewGateway gateway;
    private CurrentUserService currentUserService;
    private EvidenceReviewService service;

    @BeforeEach
    void setUp() {
        observationService = mock(HerdObservationService.class);
        gateway = mock(EvidenceReviewGateway.class);
        currentUserService = mock(CurrentUserService.class);
        service = new EvidenceReviewService(observationService, gateway, currentUserService);
        when(observationService.getLatest("NVDA")).thenReturn(observation());
        when(gateway.model()).thenReturn("test-model");
        when(currentUserService.requireUserId()).thenReturn("local");
    }

    @Test
    void disabledGatewayReturnsFactsButNeverAction() {
        when(gateway.isEnabled()).thenReturn(false);

        EvidenceReviewResponse response = service.review("NVDA");

        assertThat(response.status()).isEqualTo("DISABLED");
        assertThat(response.evidence()).extracting(EvidenceReviewResponse.EvidenceFact::id)
                .contains("OBS.STATE_SCORE", "OBS.PRICE_EXTENSION");
        assertThat(response.directionPrediction()).isFalse();
        assertThat(response.operationalAction()).isEqualTo("HOLD");
        assertThat(response.operationalActionRatio()).isEqualByComparingTo(BigDecimal.ZERO);
    }

    @Test
    void validGroundedDraftIsReturned() {
        when(gateway.isEnabled()).thenReturn(true);
        when(gateway.review(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(validDraft("OBS.STATE_SCORE"));

        EvidenceReviewResponse response = service.review("NVDA");

        assertThat(response.status()).isEqualTo("AVAILABLE");
        assertThat(response.lenses()).hasSize(4);
        assertThat(response.summary()).isEqualTo("상태 근거만 요약");
    }

    @Test
    void unknownEvidenceIdFailsClosed() {
        when(gateway.isEnabled()).thenReturn(true);
        when(gateway.review(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(validDraft("NEWS.UNKNOWN"));

        assertThat(service.review("NVDA").status()).isEqualTo("PROVIDER_ERROR");
    }

    @Test
    void actionBearingDraftFailsClosed() {
        when(gateway.isEnabled()).thenReturn(true);
        EvidenceReviewGateway.Draft draft = new EvidenceReviewGateway.Draft(
                validDraft("OBS.STATE_SCORE").lenses(), "매수", List.of(), List.of(),
                true, "BUY", 5.0
        );
        when(gateway.review(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(draft);

        EvidenceReviewResponse response = service.review("NVDA");
        assertThat(response.status()).isEqualTo("PROVIDER_ERROR");
        assertThat(response.operationalAction()).isEqualTo("HOLD");
        assertThat(response.operationalActionRatio()).isEqualByComparingTo(BigDecimal.ZERO);
    }

    private EvidenceReviewGateway.Draft validDraft(String evidenceId) {
        List<EvidenceReviewResponse.Lens> lenses = List.of(
                lens("HERD_STATE", evidenceId),
                lens("MARKET_CONTEXT", evidenceId),
                lens("RISK", evidenceId),
                lens("RED_TEAM", evidenceId)
        );
        return new EvidenceReviewGateway.Draft(
                lenses, "상태 근거만 요약", List.of(), List.of("기업 실적"),
                false, "HOLD", 0.0
        );
    }

    private EvidenceReviewResponse.Lens lens(String code, String evidenceId) {
        return new EvidenceReviewResponse.Lens(
                code, "NEUTRAL", "관찰", List.of(evidenceId), List.of()
        );
    }

    private HerdObservationResponse observation() {
        LocalDate date = LocalDate.of(2026, 7, 31);
        return new HerdObservationResponse(
                "AVAILABLE", "FRESH", 0, "NVDA", null, "NVIDIA", "Technology", null,
                "PUBLIC_RESEARCH_ONLY", "STATE_ONLY", "1", "HERD_STATE_S1",
                "HERD_TRANSITION_S1", date, date, OffsetDateTime.parse("2026-08-01T00:00:00Z"),
                BigDecimal.valueOf(62), "DRIFT", "STABLE", "STABLE", false,
                BigDecimal.valueOf(3), BigDecimal.valueOf(8),
                new HerdObservationResponse.FamilyScores(
                        BigDecimal.valueOf(70), BigDecimal.valueOf(65),
                        BigDecimal.valueOf(60), BigDecimal.valueOf(55)
                ), BigDecimal.valueOf(40), "SMH", BigDecimal.ONE,
                false, "HOLD", BigDecimal.ZERO, false
        );
    }
}
