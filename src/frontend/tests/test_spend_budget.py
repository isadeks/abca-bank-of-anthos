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
Tests for the monthly budget logic: monthly spend, usage, the warning
decision, and the calls to the budgets service (mocked)
"""

import datetime
import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

import spend_budget

ME = '1234567890'
OTHER = '9876543210'
NOW = datetime.datetime(2026, 11, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
URI = 'http://budgets:8080/budget'


def trans(sender, receiver, amount, stamp):
    """A transaction as returned by the transaction history service"""
    return {'fromAccountNum': sender, 'toAccountNum': receiver,
            'amount': amount, 'timestamp': stamp}


class TestMonthlySpend(unittest.TestCase):
    """Tests monthly_spend"""

    def test_sums_outgoing_payments_of_this_month(self):
        history = [trans(ME, OTHER, 1000, '2026-11-02T10:00:00.000+0000'),
                   trans(ME, OTHER, 250, '2026-11-14T23:59:59.999+0000')]
        self.assertEqual(spend_budget.monthly_spend(history, ME, NOW), 1250)

    def test_ignores_incoming_transactions(self):
        history = [trans(OTHER, ME, 5000, '2026-11-02T10:00:00.000+0000'),
                   trans(ME, OTHER, 700, '2026-11-03T10:00:00.000+0000')]
        self.assertEqual(spend_budget.monthly_spend(history, ME, NOW), 700)

    def test_ignores_other_months_and_years(self):
        history = [trans(ME, OTHER, 100, '2026-10-31T23:59:59.000+0000'),
                   trans(ME, OTHER, 200, '2025-11-05T10:00:00.000+0000'),
                   trans(ME, OTHER, 300, '2026-12-01T00:00:00.000+0000'),
                   trans(ME, OTHER, 400, '2026-11-01T00:00:00.000+0000')]
        self.assertEqual(spend_budget.monthly_spend(history, ME, NOW), 400)

    def test_month_is_taken_in_utc(self):
        # 2026-11-01 01:00 at +0200 is still October in UTC
        history = [trans(ME, OTHER, 100, '2026-11-01T01:00:00.000+0200')]
        self.assertEqual(spend_budget.monthly_spend(history, ME, NOW), 0)

    def test_skips_unreadable_transactions(self):
        history = [trans(ME, OTHER, 100, 'not a date'),
                   trans(ME, OTHER, 100, None),
                   trans(ME, OTHER, None, '2026-11-02T10:00:00.000+0000'),
                   trans(ME, OTHER, -50, '2026-11-02T10:00:00.000+0000'),
                   trans(ME, OTHER, 90, '2026-11-02T10:00:00.000+0000')]
        self.assertEqual(spend_budget.monthly_spend(history, ME, NOW), 90)

    def test_ignores_payment_to_self(self):
        history = [trans(ME, ME, 100, '2026-11-02T10:00:00.000+0000')]
        self.assertEqual(spend_budget.monthly_spend(history, ME, NOW), 0)

    def test_no_history(self):
        self.assertEqual(spend_budget.monthly_spend(None, ME, NOW), 0)
        self.assertEqual(spend_budget.monthly_spend([], ME, NOW), 0)

    def test_defaults_to_current_month(self):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            spend_budget.TIMESTAMP_FORMAT)
        self.assertEqual(
            spend_budget.monthly_spend([trans(ME, OTHER, 123, stamp)], ME), 123)


class TestBudgetUsage(unittest.TestCase):
    """Tests budget_usage"""

    def test_no_limit(self):
        self.assertIsNone(spend_budget.budget_usage(None, 500))
        self.assertIsNone(spend_budget.budget_usage(0, 500))

    def test_under_limit(self):
        usage = spend_budget.budget_usage(20000, 5000)
        self.assertEqual(usage, {'limit_cents': 20000, 'spent_cents': 5000,
                                 'remaining_cents': 15000, 'percent': 25,
                                 'bar_percent': 25, 'over': False})

    def test_exactly_at_limit_is_not_over(self):
        usage = spend_budget.budget_usage(10000, 10000)
        self.assertEqual(usage['percent'], 100)
        self.assertEqual(usage['remaining_cents'], 0)
        self.assertFalse(usage['over'])

    def test_over_limit(self):
        usage = spend_budget.budget_usage(10000, 15000)
        self.assertEqual(usage['percent'], 150)
        self.assertEqual(usage['bar_percent'], 100)
        self.assertEqual(usage['remaining_cents'], 0)
        self.assertTrue(usage['over'])


class TestWouldExceed(unittest.TestCase):
    """Tests the warning decision"""

    def test_no_budget_never_warns(self):
        self.assertFalse(spend_budget.would_exceed(None, 99999, 99999))

    def test_payment_within_limit(self):
        self.assertFalse(spend_budget.would_exceed(10000, 4000, 5000))

    def test_payment_landing_on_limit(self):
        self.assertFalse(spend_budget.would_exceed(10000, 4000, 6000))

    def test_payment_over_limit(self):
        self.assertTrue(spend_budget.would_exceed(10000, 4000, 6001))

    def test_already_over_limit(self):
        self.assertTrue(spend_budget.would_exceed(10000, 12000, 1))


class TestDollarsToCents(unittest.TestCase):
    """Tests dollars_to_cents"""

    def test_valid_amounts(self):
        self.assertEqual(spend_budget.dollars_to_cents('500'), 50000)
        self.assertEqual(spend_budget.dollars_to_cents(' 12.34 '), 1234)
        self.assertEqual(spend_budget.dollars_to_cents('0.01'), 1)

    def test_invalid_amounts(self):
        for text in ['', 'abc', '0', '-5', '1.234', 'NaN', 'Infinity',
                     '1e30', None]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    spend_budget.dollars_to_cents(text)


def response(status=200, body=None):
    """A mocked requests response"""
    resp = MagicMock()
    resp.json.return_value = body
    if status >= 400:
        resp.raise_for_status.side_effect = HTTPError(str(status))
    return resp


class TestBudgetCalls(unittest.TestCase):
    """Tests the calls to the budgets service with a mocked backend"""

    def test_fetch_limit(self):
        with patch('spend_budget.requests.get',
                   return_value=response(200, {'limit_cents': 50000})) as get:
            self.assertEqual(
                spend_budget.fetch_limit(URI, 'alice', 'tok', 4), (True, 50000))
        get.assert_called_once_with(
            url=URI + '/alice',
            headers={'Authorization': 'Bearer tok',
                     'content-type': 'application/json'},
            timeout=4)

    def test_fetch_limit_without_budget(self):
        with patch('spend_budget.requests.get',
                   return_value=response(200, {'limit_cents': None})):
            self.assertEqual(
                spend_budget.fetch_limit(URI, 'alice', 'tok', 4), (True, None))

    def test_fetch_limit_service_unavailable(self):
        with patch('spend_budget.requests.get',
                   side_effect=RequestsConnectionError):
            self.assertEqual(
                spend_budget.fetch_limit(URI, 'alice', 'tok', 4), (False, None))

    def test_fetch_limit_service_error(self):
        with patch('spend_budget.requests.get', return_value=response(500)):
            self.assertEqual(
                spend_budget.fetch_limit(URI, 'alice', 'tok', 4), (False, None))

    def test_fetch_limit_bad_body(self):
        resp = response(200)
        resp.json.side_effect = ValueError
        with patch('spend_budget.requests.get', return_value=resp):
            self.assertEqual(
                spend_budget.fetch_limit(URI, 'alice', 'tok', 4), (False, None))

    def test_save_limit(self):
        with patch('spend_budget.requests.put',
                   return_value=response(200, {'limit_cents': 7000})) as put:
            self.assertTrue(
                spend_budget.save_limit(URI, 'alice', 'tok', 7000, 4))
        self.assertEqual(put.call_args.kwargs['json'], {'limit_cents': 7000})
        self.assertEqual(put.call_args.kwargs['url'], URI + '/alice')

    def test_save_limit_failures(self):
        with patch('spend_budget.requests.put', return_value=response(400)):
            self.assertFalse(
                spend_budget.save_limit(URI, 'alice', 'tok', 7000, 4))
        with patch('spend_budget.requests.put',
                   side_effect=RequestsConnectionError):
            self.assertFalse(
                spend_budget.save_limit(URI, 'alice', 'tok', 7000, 4))

    def test_remove_limit(self):
        with patch('spend_budget.requests.delete',
                   return_value=response(204)) as delete:
            self.assertTrue(spend_budget.remove_limit(URI, 'alice', 'tok', 4))
        self.assertEqual(delete.call_args.kwargs['url'], URI + '/alice')

    def test_remove_limit_failures(self):
        with patch('spend_budget.requests.delete', return_value=response(500)):
            self.assertFalse(spend_budget.remove_limit(URI, 'alice', 'tok', 4))
        with patch('spend_budget.requests.delete',
                   side_effect=RequestsConnectionError):
            self.assertFalse(spend_budget.remove_limit(URI, 'alice', 'tok', 4))


if __name__ == '__main__':
    unittest.main()
