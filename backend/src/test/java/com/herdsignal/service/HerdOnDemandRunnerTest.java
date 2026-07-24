package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class HerdOnDemandRunnerTest {
    private final HerdOnDemandRunner runner = new HerdOnDemandRunner(
            new ObjectMapper(), new PythonProcessGateway(""));

    @Test
    void normalizesAndDeduplicatesTickers() {
        assertThat(runner.normalizeTickers(List.of(" nvda ", "NVDA", "brk.b")))
                .containsExactly("NVDA", "BRK.B");
    }

    @Test
    void rejectsUnsafeTicker() {
        assertThatThrownBy(() -> runner.normalizeTickers(List.of("NVDA'); import os")))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void surfacesPartialBatchFailure() {
        String output = "log line\n{\"results\": {}, \"errors\": [{\"ticker\": \"BAD\"}]}";
        assertThatThrownBy(() -> runner.failOnBatchErrors(output))
                .isInstanceOf(IOException.class)
                .hasMessageContaining("일부 HERD 갱신 실패");
    }

    @Test
    void acceptsBatchWithoutErrors() throws IOException {
        runner.failOnBatchErrors("{\"results\": {\"NVDA\": {}}, \"errors\": []}");
    }

}
