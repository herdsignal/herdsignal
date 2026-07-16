package com.herdsignal.service;

import com.herdsignal.dto.InvestorProfileRequest;
import com.herdsignal.dto.RebalanceSettingsRequest;
import com.herdsignal.repository.InvestorProfileRepository;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.any;

class InvestorProfileServiceTest {
    private final InvestorProfileRepository repository = mock(InvestorProfileRepository.class);
    private final InvestorProfileService service = new InvestorProfileService(repository);

    @Test
    void rejectsUnsafeActionRatio() {
        assertThatThrownBy(() -> service.update("local", request("0.50")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("1회 최대 행동비율");
    }

    @Test
    void rejectsUnknownStrategy() {
        InvestorProfileRequest request = new InvestorProfileRequest(
                "ALL_IN", "BALANCED", 10, 6, new BigDecimal("0.10"), new BigDecimal("0.70"));

        assertThatThrownBy(() -> service.update("local", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("투자 방식");
    }

    @Test
    void savesRebalanceSettingsInUserProfile() {
        when(repository.findById("local")).thenReturn(Optional.empty());
        when(repository.save(any())).thenAnswer(invocation -> invocation.getArgument(0));

        var response = service.updateRebalanceSettings(
                "local",
                new RebalanceSettingsRequest(
                        new BigDecimal("2500"),
                        new BigDecimal("0.15"),
                        "aggressive"
                )
        );

        org.assertj.core.api.Assertions.assertThat(response.budget()).isEqualByComparingTo("2500.00");
        org.assertj.core.api.Assertions.assertThat(response.cashTargetRatio()).isEqualByComparingTo("0.15");
        org.assertj.core.api.Assertions.assertThat(response.mode()).isEqualTo("AGGRESSIVE");
    }

    private InvestorProfileRequest request(String maxRatio) {
        when(repository.findById("local")).thenReturn(Optional.empty());
        return new InvestorProfileRequest(
                "NEW_ENTRY", "BALANCED", 10, 6, new BigDecimal(maxRatio), new BigDecimal("0.70"));
    }
}
