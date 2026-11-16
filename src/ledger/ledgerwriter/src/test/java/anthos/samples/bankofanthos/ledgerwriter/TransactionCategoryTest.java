package anthos.samples.bankofanthos.ledgerwriter;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class TransactionCategoryTest {

    private static Transaction parse(String categoryJson) throws Exception {
        String json = "{\"fromAccountNum\":\"1\",\"fromRoutingNum\":\"2\","
            + "\"toAccountNum\":\"3\",\"toRoutingNum\":\"4\",\"amount\":5,"
            + "\"uuid\":\"u\"" + categoryJson + "}";
        return new ObjectMapper().readValue(json, Transaction.class);
    }

    @Test
    void missingCategoryIsOther() throws Exception {
        assertEquals("Other", parse("").getCategory());
    }

    @Test
    void nullCategoryIsOther() throws Exception {
        assertEquals("Other", parse(",\"category\":null").getCategory());
    }

    @Test
    void unknownCategoryIsOther() throws Exception {
        assertEquals("Other", parse(",\"category\":\"Yachts\"").getCategory());
    }

    @Test
    void knownCategoriesAreKept() throws Exception {
        for (String c : Transaction.CATEGORIES) {
            assertEquals(c, parse(",\"category\":\"" + c + "\"").getCategory());
        }
    }

    @Test
    void categoryMatchIsCaseInsensitive() throws Exception {
        assertEquals("Eating out",
            parse(",\"category\":\"eating OUT\"").getCategory());
    }
}
