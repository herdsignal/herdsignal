package com.herdsignal.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class PythonProcessGatewayTest {

    @Test
    void findsProjectRootFromBackendDirectory(@TempDir Path tempDir) throws IOException {
        Files.createDirectory(tempDir.resolve("data"));
        Path backend = Files.createDirectory(tempDir.resolve("backend"));

        assertThat(new PythonProcessGateway("").findProjectRoot(backend)).isEqualTo(tempDir);
    }
}
