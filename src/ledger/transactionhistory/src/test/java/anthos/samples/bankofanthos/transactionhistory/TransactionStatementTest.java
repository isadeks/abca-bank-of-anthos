package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.cache.LoadingCache;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.Date;
import java.util.Deque;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;

class TransactionStatementTest {

    private static final String ROUTING = "123456789";
    private static final String ACCT = "1234567890";
    private static final String OTHER = "9876543210";

    private TransactionHistoryController controller;
    private TransactionRepository repo;
    private JWTVerifier verifier;

    @SuppressWarnings("unchecked")
    @BeforeEach
    void setUp() {
        verifier = mock(JWTVerifier.class);
        repo = mock(TransactionRepository.class);
        LoadingCache<String, Deque<Transaction>> cache =
            mock(LoadingCache.class);
        when(cache.stats()).thenReturn(new com.google.common.cache.CacheStats(0, 0, 0, 0, 0, 0));
        controller = new TransactionHistoryController(
            mock(LedgerReader.class), new SimpleMeterRegistry(), verifier,
            "path/", cache, ROUTING, "v1");
        ReflectionTestUtils.setField(controller, "dbRepo", repo);

        DecodedJWT jwt = mock(DecodedJWT.class);
        Claim claim = mock(Claim.class);
        when(verifier.verify("abc")).thenReturn(jwt);
        when(jwt.getClaim("acct")).thenReturn(claim);
        when(claim.asString()).thenReturn(ACCT);
    }

    private static Transaction tx(String from, String to, int amount,
                                  long epochMillis) {
        Transaction t = new Transaction();
        ReflectionTestUtils.setField(t, "fromAccountNum", from);
        ReflectionTestUtils.setField(t, "fromRoutingNum", ROUTING);
        ReflectionTestUtils.setField(t, "toAccountNum", to);
        ReflectionTestUtils.setField(t, "toRoutingNum", ROUTING);
        ReflectionTestUtils.setField(t, "amount", amount);
        ReflectionTestUtils.setField(t, "timestamp", new Date(epochMillis));
        return t;
    }

    @Test
    void statementReturnsCsvForMonth() {
        // 2024-03-05 and 2024-03-20 (UTC)
        when(repo.findForAccountBetween(eq(ACCT), eq(ROUTING),
                any(Date.class), any(Date.class)))
            .thenReturn(List.of(
                tx(ACCT, OTHER, 12345, 1709600000000L),
                tx(OTHER, ACCT, 500, 1710900000000L)));

        ResponseEntity<?> res =
            controller.getStatement("Bearer abc", ACCT, "2024-03");

        assertEquals(HttpStatus.OK, res.getStatusCode());
        assertTrue(res.getHeaders().getFirst(HttpHeaders.CONTENT_TYPE)
            .startsWith("text/csv"));
        assertTrue(res.getHeaders().getFirst(HttpHeaders.CONTENT_DISPOSITION)
            .contains("statement-2024-03.csv"));
        assertEquals("date,type,counterparty,amount\n"
            + "2024-03-05,debit," + OTHER + ",-123.45\n"
            + "2024-03-20,credit," + OTHER + ",5.00\n", res.getBody());
        verify(repo).findForAccountBetween(ACCT, ROUTING,
            new Date(1709251200000L), new Date(1711929600000L));
    }

    @Test
    void statementRejectsBadMonth() {
        ResponseEntity<?> res =
            controller.getStatement("Bearer abc", ACCT, "March");
        assertEquals(HttpStatus.BAD_REQUEST, res.getStatusCode());
    }

    @Test
    void statementRejectsBadAccountId() {
        ResponseEntity<?> res =
            controller.getStatement("Bearer abc", "12ab", "2024-03");
        assertEquals(HttpStatus.BAD_REQUEST, res.getStatusCode());
    }

    @Test
    void statementRejectsOtherAccount() {
        ResponseEntity<?> res =
            controller.getStatement("Bearer abc", OTHER, "2024-03");
        assertEquals(HttpStatus.UNAUTHORIZED, res.getStatusCode());
    }

    @Test
    void statementRejectsInvalidToken() {
        when(verifier.verify("abc"))
            .thenThrow(JWTVerificationException.class);
        ResponseEntity<?> res =
            controller.getStatement("Bearer abc", ACCT, "2024-03");
        assertEquals(HttpStatus.UNAUTHORIZED, res.getStatusCode());
    }
}
