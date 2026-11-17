# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for filtering the transaction history."""

import unittest

from frontend import filter_transactions

ME = '1111111111'
HISTORY = [
    {'fromAccountNum': '2222222222', 'toAccountNum': ME, 'amount': 100,
     'accountLabel': 'Alice'},
    {'fromAccountNum': ME, 'toAccountNum': '3333333333', 'amount': 50,
     'accountLabel': 'Bob'},
    {'fromAccountNum': ME, 'toAccountNum': '4444444444', 'amount': 5,
     'accountLabel': None},
]


class TestFilterTransactions(unittest.TestCase):
    """filter_transactions narrows the list by type and text"""

    def test_all_returns_everything(self):
        self.assertEqual(filter_transactions(HISTORY, ME), HISTORY)

    def test_credit_only(self):
        res = filter_transactions(HISTORY, ME, 'credit')
        self.assertEqual(res, [HISTORY[0]])

    def test_debit_only(self):
        res = filter_transactions(HISTORY, ME, 'debit')
        self.assertEqual(res, HISTORY[1:])

    def test_query_matches_label_case_insensitive(self):
        self.assertEqual(filter_transactions(HISTORY, ME, 'all', 'bOb'),
                         [HISTORY[1]])

    def test_query_matches_other_account(self):
        self.assertEqual(filter_transactions(HISTORY, ME, 'all', '4444'),
                         [HISTORY[2]])

    def test_combined(self):
        self.assertEqual(filter_transactions(HISTORY, ME, 'credit', 'bob'), [])

    def test_none_history_is_kept(self):
        self.assertIsNone(filter_transactions(None, ME, 'credit'))


if __name__ == '__main__':
    unittest.main()
