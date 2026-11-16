package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.cache.LoadingCache;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Deque;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

class TransactionCategoryTest {

    private static final String ACCT = "1234567890";
    private static final String ROUTING = "123456789";

    private TransactionHistoryController controller;
    private TransactionRepository repo;
    private LoadingCache<String, Deque<Transaction>> cache;

    @SuppressWarnings("unchecked")
    @BeforeEach
    void setUp() throws Exception {
        JWTVerifier verifier = mock(JWTVerifier.class);
        DecodedJWT jwt = mock(DecodedJWT.class);
        Claim claim = mock(Claim.class);
        cache = mock(LoadingCache.class);
        when(cache.stats()).thenReturn(
            new com.google.common.cache.CacheStats(0, 0, 0, 0, 0, 0));
        repo = mock(TransactionRepository.class);
        when(verifier.verify("abc")).thenReturn(jwt);
        when(jwt.getClaim("acct")).thenReturn(claim);
        when(claim.asString()).thenReturn(ACCT);
        controller = new TransactionHistoryController(
            mock(LedgerReader.class), new SimpleMeterRegistry(), verifier,
            "path/", cache, ROUTING, "v");
        Field f = TransactionHistoryController.class
            .getDeclaredField("dbRepo");
        f.setAccessible(true);
        f.set(controller, repo);
        Deque<Transaction> history = new LinkedList<>();
        history.add(tx("Groceries", 100));
        history.add(tx(null, 200));
        history.add(tx("Rent", 300));
        history.add(tx("Groceries", 400));
        when(cache.get(ACCT)).thenReturn(history);
    }

    private static Transaction tx(String category, int amount)
            throws Exception {
        String cat = category == null
            ? "" : ",\"category\":\"" + category + "\"";
        return new ObjectMapper().readValue(String.format(
            "{\"fromAccountNum\":\"%s\",\"fromRoutingNum\":\"%s\","
            + "\"toAccountNum\":\"9999999999\",\"toRoutingNum\":\"%s\","
            + "\"amount\":%d%s}", ACCT, ROUTING, ROUTING, amount, cat),
            Transaction.class);
    }

    @SuppressWarnings("unchecked")
    private List<Transaction> list(ResponseEntity<?> r) {
        assertEquals(HttpStatus.OK, r.getStatusCode());
        return new ArrayList<>((Collection<Transaction>) r.getBody());
    }

    @Test
    void withoutCategoryAllTransactionsAreReturned() {
        assertEquals(4, list(
            controller.getTransactions("Bearer abc", ACCT)).size());
        assertEquals(4, list(
            controller.getTransactions("Bearer abc", ACCT, "")).size());
    }

    @Test
    void missingCategoryIsReportedAsOther() throws Exception {
        assertEquals("Other", tx(null, 1).getCategory());
        assertEquals("Other", tx("Bogus", 1).getCategory());
        assertTrue(new ObjectMapper().writeValueAsString(tx(null, 1))
            .contains("\"category\":\"Other\""));
    }

    @Test
    void filterByCategory() {
        List<Transaction> groceries = list(
            controller.getTransactions("Bearer abc", ACCT, "Groceries"));
        assertEquals(2, groceries.size());
        List<Transaction> other = list(
            controller.getTransactions("Bearer abc", ACCT, "other"));
        assertEquals(1, other.size());
        assertEquals(200, other.get(0).getAmount());
    }

    @Test
    void unknownCategoryFilterIsBadRequest() {
        assertEquals(HttpStatus.BAD_REQUEST, controller.getTransactions(
            "Bearer abc", ACCT, "Gambling").getStatusCode());
    }

    @Test
    @SuppressWarnings("unchecked")
    void spendingPerCategory() {
        List<Object[]> rows = new ArrayList<>();
        rows.add(new Object[] {"Groceries", 500L});
        rows.add(new Object[] {null, 70L});
        rows.add(new Object[] {"Other", 30L});
        when(repo.sumSpentByCategory(eq(ACCT), eq(ROUTING), any(), any()))
            .thenReturn(rows);

        ResponseEntity<?> r =
            controller.getMonthlySpending("Bearer abc", ACCT);

        assertEquals(HttpStatus.OK, r.getStatusCode());
        Map<String, Long> totals = (Map<String, Long>) r.getBody();
        assertEquals(500L, totals.get("Groceries"));
        assertEquals(100L, totals.get("Other"));
        assertEquals(0L, totals.get("Rent"));
        assertEquals(5, totals.size());
    }

    @Test
    void spendingRequiresMatchingAccount() {
        assertEquals(HttpStatus.UNAUTHORIZED,
            controller.getMonthlySpending("Bearer abc", "5555555555")
                .getStatusCode());
        assertEquals(HttpStatus.BAD_REQUEST,
            controller.getMonthlySpending("Bearer abc", "abc")
                .getStatusCode());
    }
}
