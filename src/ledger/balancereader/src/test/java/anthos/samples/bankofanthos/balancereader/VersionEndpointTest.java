package anthos.samples.bankofanthos.balancereader;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.google.common.cache.CacheStats;
import com.google.common.cache.LoadingCache;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

/** Tests the /version endpoint, including the "unknown" fallback. */
class VersionEndpointTest {

    @SuppressWarnings("unchecked")
    private BalanceReaderController controller(String version) {
        LoadingCache<String, Long> cache = mock(LoadingCache.class);
        when(cache.stats()).thenReturn(new CacheStats(0, 0, 0, 0, 0, 0));
        return new BalanceReaderController(mock(LedgerReader.class),
            mock(JWTVerifier.class), new SimpleMeterRegistry(),
            cache, "123456789", version);
    }

    @Test
    void returnsConfiguredVersion() {
        ResponseEntity<?> r = controller("v1.2.3").version();
        assertEquals(HttpStatus.OK, r.getStatusCode());
        assertEquals("v1.2.3", r.getBody());
    }

    @Test
    void returnsUnknownWhenVersionNotSet() {
        assertEquals("unknown", controller(null).version().getBody());
        assertEquals("unknown", controller("").version().getBody());
    }
}
