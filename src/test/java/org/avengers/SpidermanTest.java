package org.avengers;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

import java.util.Random;
import org.junit.jupiter.api.Test;

/**
 * Unit test for simple App.
 */
public class SpidermanTest {

    private static final Random random = new Random();

    /**
     * Rigorous Test :-)
     */
    @Test
    public void shouldAnswerWithTrue() {
        boolean flag = random.nextInt(10) % 2 == 0;
        if (flag) {
            assertTrue(true);
        } else {
            fail();
        }
    }
}
