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

"""
Tests for the "Spending this month" aggregation on the home page
"""

import datetime
import unittest

import frontend

FMT = '%Y-%m-%dT%H:%M:%S.%f%z'
ME = '1111111111'
NOW = datetime.datetime(2026, 11, 8, 12, 0, tzinfo=datetime.timezone.utc)
CONTACTS = [
    {'account_num': '2222222222', 'label': 'Alice'},
    {'account_num': '3333333333', 'label': 'Bob'},
]


def tx(to_acct, cents, stamp='2026-11-02T10:00:00.000+0000', from_acct=ME):
    """Build a transaction dict like the history service returns"""
    return {'fromAccountNum': from_acct, 'toAccountNum': to_acct,
            'amount': cents, 'timestamp': stamp}


def spend(transactions, contacts=None, **kwargs):
    """Call spending_by_contact with test defaults"""
    return frontend.spending_by_contact(
        ME, transactions, CONTACTS if contacts is None else contacts,
        NOW, FMT, **kwargs)


class TestSpendingByContact(unittest.TestCase):
    """Tests frontend.spending_by_contact"""

    def test_sums_per_contact_largest_first(self):
        """payments to the same contact are summed and sorted descending"""
        result = spend([tx('2222222222', 1000), tx('3333333333', 5000),
                        tx('2222222222', 2500)])
        self.assertEqual(
            [(r['label'], r['amount']) for r in result],
            [('Bob', 5000), ('Alice', 3500)])

    def test_only_this_calendar_month(self):
        """payments from other months or years are ignored"""
        result = spend([
            tx('2222222222', 1000, '2026-10-31T23:59:59.000+0000'),
            tx('2222222222', 1000, '2025-11-05T10:00:00.000+0000'),
            tx('2222222222', 700, '2026-11-01T00:00:00.000+0000')])
        self.assertEqual([r['amount'] for r in result], [700])

    def test_month_boundary_uses_utc(self):
        """a timestamp with an offset is compared in UTC"""
        result = spend([tx('2222222222', 100, '2026-10-31T20:00:00.000-0800')])
        self.assertEqual([r['amount'] for r in result], [100])

    def test_ignores_credits_and_non_contacts(self):
        """money received, and payments to non-contacts, do not count"""
        result = spend([
            tx(ME, 9000, from_acct='2222222222'),
            tx('9999999999', 9000),
            tx('3333333333', 400)])
        self.assertEqual([(r['label'], r['amount']) for r in result],
                         [('Bob', 400)])

    def test_top_five_only(self):
        """at most five contacts are returned"""
        contacts = [{'account_num': str(i) * 10, 'label': 'C%d' % i}
                    for i in range(1, 8)]
        txs = [tx(str(i) * 10, i * 100) for i in range(1, 8)]
        result = spend(txs, contacts=contacts)
        self.assertEqual([r['label'] for r in result],
                         ['C7', 'C6', 'C5', 'C4', 'C3'])

    def test_missing_data_gives_empty(self):
        """None transactions/contacts or no payments give an empty list"""
        self.assertEqual(spend(None), [])
        self.assertEqual(frontend.spending_by_contact(ME, [], None, NOW, FMT), [])
        self.assertEqual(spend([]), [])

    def test_bad_timestamp_skipped(self):
        """a transaction with an unparsable timestamp is skipped"""
        result = spend([tx('2222222222', 100, 'garbage'), tx('2222222222', 50)])
        self.assertEqual([r['amount'] for r in result], [50])


if __name__ == '__main__':
    unittest.main()
