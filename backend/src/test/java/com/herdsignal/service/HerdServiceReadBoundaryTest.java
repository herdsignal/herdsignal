package com.herdsignal.service;

import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.HerdIndicatorRepository;
import com.herdsignal.repository.HerdScoreRepository;
import com.herdsignal.repository.StockRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class HerdServiceReadBoundaryTest {

    @Test
    void missingReadNeverStartsPythonRefresh() {
        HerdScoreRepository scoreRepository = mock(HerdScoreRepository.class);
        HerdOnDemandRunner runner = mock(HerdOnDemandRunner.class);
        HerdService service = new HerdService(
                mock(UserPortfolioRepository.class),
                scoreRepository,
                mock(HerdIndicatorRepository.class),
                mock(StockRepository.class),
                mock(HerdResponseAssembler.class),
                mock(ActionCooldownService.class),
                mock(PortfolioActionContextService.class),
                mock(InvestorProfileService.class),
                runner
        );
        when(scoreRepository.findTopByTickerOrderByScoreDateDesc("NVDA"))
                .thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getStockHerd("NVDA", null))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("새로고침");
        verifyNoInteractions(runner);
    }
}
