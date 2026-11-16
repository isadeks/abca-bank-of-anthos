package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.core.env.MapPropertySource;
import java.util.Map;

/**
 * Integration test of the category queries against the real ledger
 * database. Runs only when SPRING_DATASOURCE_* are set.
 */
class TransactionCategoryIT {

    private static final String ROUTING = "883745000";

    private static AnnotationConfigApplicationContext context;
    private static TransactionRepository repository;

    @BeforeAll
    static void setUp() {
        context = new AnnotationConfigApplicationContext();
        context.getEnvironment().getPropertySources().addFirst(
            new MapPropertySource("it", Map.of("LOCAL_ROUTING_NUM", ROUTING)));
        context.register(LedgerDbTestConfig.class);
        context.refresh();
        repository = context.getBean(TransactionRepository.class);
    }

    @AfterAll
    static void tearDown() {
        if (context != null) {
            context.close();
        }
    }

    private static String newAccountNum() {
        return String.valueOf(ThreadLocalRandom.current()
            .nextLong(1_000_000_000L, 10_000_000_000L));
    }

    private static Transaction save(String from, String to, int amount,
            String category) throws Exception {
        String cat = category == null
            ? "" : ",\"category\":\"" + category + "\"";
        return repository.save(new ObjectMapper().readValue(String.format(
            "{\"fromAccountNum\":\"%s\",\"fromRoutingNum\":\"%s\","
            + "\"toAccountNum\":\"%s\",\"toRoutingNum\":\"%s\","
            + "\"amount\":%d%s}", from, ROUTING, to, ROUTING, amount, cat),
            Transaction.class));
    }

    @Test
    void categoryIsStoredAndTotalsAreSummedPerCategory() throws Exception {
        String alice = newAccountNum();
        String bob = newAccountNum();
        save(alice, bob, 1000, "Groceries");
        save(alice, bob, 250, "Groceries");
        save(alice, bob, 400, null);
        save(bob, alice, 9999, "Rent"); // income, not spending

        List<Object[]> rows = repository.sumSpentByCategory(alice, ROUTING,
            LocalDateTime.now().minusDays(1), LocalDateTime.now().plusDays(1));

        assertEquals(2, rows.size());
        for (Object[] row : rows) {
            if ("Groceries".equals(row[0])) {
                assertEquals(1250L, ((Number) row[1]).longValue());
            } else {
                assertEquals("Other", row[0]);
                assertEquals(400L, ((Number) row[1]).longValue());
            }
        }
    }

    @Test
    void periodOutsideRangeIsExcluded() throws Exception {
        String alice = newAccountNum();
        save(alice, newAccountNum(), 100, "Rent");
        assertEquals(0, repository.sumSpentByCategory(alice, ROUTING,
            LocalDateTime.now().minusYears(2),
            LocalDateTime.now().minusYears(1)).size());
    }
}
