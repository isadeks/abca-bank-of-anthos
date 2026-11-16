package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import javax.sql.DataSource;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.core.env.MapPropertySource;
import org.springframework.data.domain.PageRequest;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Integration test of the category queries against the real ledger
 * database. Runs only when SPRING_DATASOURCE_* are set.
 *
 * Works with ledger databases with and without the CATEGORY column: without
 * it, everything is reported as "Other".
 */
class TransactionCategoryIT {

    private static final String ROUTING = "883745000";

    private static AnnotationConfigApplicationContext context;
    private static TransactionRepository repository;
    private static JdbcTemplate jdbc;
    private static boolean hasCategoryColumn;

    @BeforeAll
    static void setUp() {
        context = new AnnotationConfigApplicationContext();
        context.getEnvironment().getPropertySources().addFirst(
            new MapPropertySource("it", Map.of("LOCAL_ROUTING_NUM", ROUTING)));
        context.register(LedgerDbTestConfig.class);
        context.refresh();
        repository = context.getBean(TransactionRepository.class);
        jdbc = new JdbcTemplate(context.getBean(DataSource.class));
        hasCategoryColumn = jdbc.queryForObject(
            "SELECT COUNT(*) FROM information_schema.columns "
            + "WHERE table_name = 'transactions' "
            + "AND column_name = 'category'", Integer.class) > 0;
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

    private static void insert(String from, String to, int amount,
            String category) {
        if (category != null) {
            jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, FROM_ROUTE, "
                + "TO_ACCT, TO_ROUTE, AMOUNT, TIMESTAMP, CATEGORY) "
                + "VALUES (?, ?, ?, ?, ?, NOW(), ?)",
                from, ROUTING, to, ROUTING, amount, category);
        } else {
            jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, FROM_ROUTE, "
                + "TO_ACCT, TO_ROUTE, AMOUNT, TIMESTAMP) "
                + "VALUES (?, ?, ?, ?, ?, NOW())",
                from, ROUTING, to, ROUTING, amount);
        }
    }

    @Test
    void categoriesAreLoadedAndSummed() {
        assumeTrue(hasCategoryColumn, "ledger has no CATEGORY column");
        String alice = newAccountNum();
        String bob = newAccountNum();
        insert(alice, bob, 1000, "Groceries");
        insert(alice, bob, 250, "Groceries");
        insert(alice, bob, 400, null);
        insert(bob, alice, 9999, "Rent"); // income, not spending

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

        List<Transaction> history = repository.findForAccount(
            alice, ROUTING, PageRequest.of(0, 10));
        repository.loadCategories(history);
        assertEquals(4, history.size());
        long groceries = history.stream()
            .filter(t -> "Groceries".equals(t.getCategory())).count();
        long rent = history.stream()
            .filter(t -> "Rent".equals(t.getCategory())).count();
        assertEquals(2, groceries);
        assertEquals(1, rent);
    }

    @Test
    void historyAndTotalWorkWhateverTheSchema() {
        String alice = newAccountNum();
        insert(alice, newAccountNum(), 700, null);

        List<Transaction> history = repository.findForAccount(
            alice, ROUTING, PageRequest.of(0, 10));
        repository.loadCategories(history);
        assertEquals(1, history.size());
        assertEquals("Other", history.get(0).getCategory());
        assertEquals(700L, repository.sumSpent(alice, ROUTING,
            LocalDateTime.now().minusDays(1),
            LocalDateTime.now().plusDays(1)));
    }

    @Test
    void periodOutsideRangeIsExcluded() {
        String alice = newAccountNum();
        insert(alice, newAccountNum(), 100, null);
        Long total = repository.sumSpent(alice, ROUTING,
            LocalDateTime.now().minusYears(2),
            LocalDateTime.now().minusYears(1));
        assertEquals(null, total);
    }
}
