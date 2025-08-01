package org.avengers;

import static org.junit.jupiter.api.Assertions.fail;

import org.junit.jupiter.api.Test;

public class CIExecutionCounterTest {

    @Test
    public void shouldFailWhenSimulateFailureIsTrue() {
        String simulateFailure = System.getProperty("SIMULATE_FAILURE", "false");
        // Check for repository variable first
        if ("true".equalsIgnoreCase(simulateFailure)) {
            fail("Test intentionally failed because SIMULATE_FAILURE repository variable is set to 'true'");
        }
    }
}
