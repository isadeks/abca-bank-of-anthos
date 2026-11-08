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
Tests for the home page's activity summary and debit/credit styling
"""

import os
import unittest
from unittest.mock import patch, mock_open

from requests.exceptions import RequestException

import frontend

ACCOUNT = '1234567890'
OTHER = '0987654321'

BASE_ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
}


def _transaction(from_acct, to_acct, amount):
    return {'fromAccountNum': from_acct, 'toAccountNum': to_acct, 'amount': amount,
            'timestamp': '2026-01-02T03:04:05.000000+0000', 'accountLabel': None}


class TestSummarizeTransactions(unittest.TestCase):
    """Tests the totals shown in the activity summary"""

    def test_totals_money_in_and_out(self):
        """credits add to money_in, debits to money_out, and each counts once"""
        history = [_transaction(OTHER, ACCOUNT, 10000),
                   _transaction(ACCOUNT, OTHER, 2550),
                   _transaction(OTHER, ACCOUNT, 500)]
        self.assertEqual(frontend.summarize_transactions(ACCOUNT, history),
                         {'money_in': 10500, 'money_out': 2550, 'count': 3})

    def test_ignores_transactions_of_other_accounts(self):
        """a transaction not involving the account is not counted"""
        history = [_transaction(OTHER, '1111111111', 999)]
        self.assertEqual(frontend.summarize_transactions(ACCOUNT, history),
                         {'money_in': 0, 'money_out': 0, 'count': 0})

    def test_missing_history(self):
        """a failed history lookup (None) or an empty one gives zero totals"""
        zero = {'money_in': 0, 'money_out': 0, 'count': 0}
        self.assertEqual(frontend.summarize_transactions(ACCOUNT, None), zero)
        self.assertEqual(frontend.summarize_transactions(ACCOUNT, []), zero)


class TestHomeTemplate(unittest.TestCase):
    """Tests how the home template shows the summary and debit/credit rows"""

    def setUp(self):
        with patch('frontend.open', mock_open(read_data='foo')), \
                patch('os.environ', dict(BASE_ENV)), \
                patch('frontend.requests.get', side_effect=RequestException):
            self.app = frontend.create_app()

    def _render(self, history):
        summary = frontend.summarize_transactions(ACCOUNT, history)
        with self.app.test_request_context('/home'):
            return frontend.render_template(
                'index.html', account_id=ACCOUNT, balance=123456, bank_name='Bank',
                cluster_name=None, contacts=[], cymbal_logo='false', history=history,
                summary=summary, message=None, name='Test', platform=None,
                platform_display_name=None, pod_name=None, pod_zone=None)

    def test_summary_and_styled_rows(self):
        """money in/out totals are shown and each row has a credit or debit badge"""
        html = self._render([_transaction(OTHER, ACCOUNT, 10000),
                             _transaction(ACCOUNT, OTHER, 2550)])
        self.assertIn('id="summary-money-in"', html)
        self.assertIn('$100.00', html)
        self.assertIn('$25.50', html)
        self.assertIn('type-badge-credit', html)
        self.assertIn('type-badge-debit', html)
        self.assertIn('+$100.00', html)
        self.assertIn('-$25.50', html)
        self.assertIn('$1,234.56', html)

    def test_no_summary_without_history(self):
        """the summary is left out when there are no transactions to summarize"""
        for history in ([], None):
            html = self._render(history)
            self.assertNotIn('id="activity-summary"', html)
            self.assertIn('id="current-balance"', html)


if __name__ == '__main__':
    unittest.main()
