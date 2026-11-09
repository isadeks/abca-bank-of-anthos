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

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;

/**
 * Guards the shape of the history query: it must stay a union of two limited,
 * newest-first scans (one per index of the ledger) and must not go back to a
 * single OR condition, which forces the database to sort the whole account
 * before the page size applies. TransactionHistoryQueryPlanIT checks the plan
 * the database really picks.
 */
class TransactionRepositoryQueryTest {

    private static String historyQuery() throws NoSuchMethodException {
        return TransactionRepository.class
            .getMethod("findForAccount", String.class, String.class,
                Pageable.class)
            .getAnnotation(Query.class)
            .value()
            .toUpperCase();
    }

    @Test
    @DisplayName("The history query is a native query")
    void historyQueryIsNative() throws Exception {
        assertTrue(TransactionRepository.class
            .getMethod("findForAccount", String.class, String.class,
                Pageable.class)
            .getAnnotation(Query.class)
            .nativeQuery());
    }

    @Test
    @DisplayName("The history query reads the sender and the receiver index "
        + "separately, each newest first and limited to the page")
    void historyQueryUsesTwoLimitedIndexScans() throws Exception {
        String query = historyQuery();

        assertTrue(query.contains(" UNION "));
        assertFalse(query.contains(" OR "));
        assertTrue(query.contains("FROM_ACCT = CAST(?1 AS CHAR(10))"));
        assertTrue(query.contains("FROM_ROUTE = CAST(?2 AS CHAR(9))"));
        assertTrue(query.contains("TO_ACCT = CAST(?1 AS CHAR(10))"));
        assertTrue(query.contains("TO_ROUTE = CAST(?2 AS CHAR(9))"));
        // Both branches and the final result are ordered newest first.
        assertEquals(3, count(query, "ORDER BY TIMESTAMP DESC"));
        // Both branches stop after the page.
        assertEquals(2, count(query, "LIMIT "));
    }

    private static int count(String text, String part) {
        return text.split(java.util.regex.Pattern.quote(part), -1).length - 1;
    }
}
