/*
 * Copyright 2026, Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.LocalDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.jpa.repository.Query;

/**
 * Guards the shape of the spending query: a grouped query over the outgoing
 * rows of the account, bounded below by a timestamp so that the
 * (FROM_ACCT, FROM_ROUTE, TIMESTAMP) index limits the rows read, and never
 * limited to a page (which would give wrong totals).
 * TransactionHistorySpendingQueryPlanIT checks the plan the database picks.
 */
class TransactionRepositorySpendingQueryTest {

    private static Query annotation() throws NoSuchMethodException {
        return TransactionRepository.class
            .getMethod("spendingByCounterparty", String.class, String.class,
                LocalDateTime.class)
            .getAnnotation(Query.class);
    }

    private static String spendingQuery() throws NoSuchMethodException {
        return annotation().value().toUpperCase();
    }

    @Test
    @DisplayName("The spending query is a native query")
    void spendingQueryIsNative() throws Exception {
        assertTrue(annotation().nativeQuery());
    }

    @Test
    @DisplayName("The spending query sums the outgoing rows of the account "
        + "per month and counterparty")
    void spendingQueryGroupsOutgoingRows() throws Exception {
        String query = spendingQuery();

        assertTrue(query.contains("SUM(AMOUNT)"));
        assertTrue(query.contains("GROUP BY"));
        assertTrue(query.contains("DATE_TRUNC('MONTH', TIMESTAMP)"));
        assertTrue(query.contains("TO_ACCT"));
        assertTrue(query.contains("TO_ROUTE"));
        assertTrue(query.contains("FROM_ACCT = CAST(?1 AS CHAR(10))"));
        assertTrue(query.contains("FROM_ROUTE = CAST(?2 AS CHAR(9))"));
        assertFalse(query.contains(" OR "));
    }

    @Test
    @DisplayName("The spending query is bounded by the start timestamp and "
        + "not by a row limit")
    void spendingQueryIsBoundedByTimestampNotByLimit() throws Exception {
        String query = spendingQuery();

        assertTrue(query.contains("TIMESTAMP >= CAST(?3 AS TIMESTAMP)"));
        assertFalse(query.contains("LIMIT"));
    }

    @Test
    @DisplayName("The spending query leaves out transfers to oneself")
    void spendingQueryExcludesSelfTransfers() throws Exception {
        assertTrue(spendingQuery().contains(
            "NOT (TO_ACCT = FROM_ACCT AND TO_ROUTE = FROM_ROUTE)"));
    }
}
