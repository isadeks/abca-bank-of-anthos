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
Tests for the paginated transaction history (home page + /history)
"""

import os
import unittest
from unittest.mock import MagicMock, mock_open, patch

from requests.exceptions import RequestException

import frontend

ACCOUNT = '1234567890'
OTHER = '9876543210'
ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'TRANSACTIONS_API_ADDR': 'ledgerwriter',
    'USERSERVICE_API_ADDR': 'userservice',
    'BALANCES_API_ADDR': 'balances',
    'HISTORY_API_ADDR': 'history',
    'CONTACTS_API_ADDR': 'contacts',
}
CLAIMS = {'user': 'testuser', 'acct': ACCOUNT, 'name': 'Test User'}


def make_transactions(count):
    """Most recent first; amounts are 100, 200, ... so rows can be told apart"""
    return [{
        'transactionId': i,
        'fromAccountNum': OTHER if i % 2 else ACCOUNT,
        'toAccountNum': ACCOUNT if i % 2 else OTHER,
        'amount': (i + 1) * 100,
        'timestamp': '2026-01-01T10:00:00.000+0000',
    } for i in range(count)]


def fake_response(payload):
    """A successful requests response returning payload"""
    response = MagicMock()
    response.__bool__ = lambda self: True
    response.json.return_value = payload
    return response


class HistoryPaginationTest(unittest.TestCase):
    """Home page shows 10 transactions, /history serves the next pages"""

    def setUp(self):
        with patch('frontend.open', mock_open(read_data='foo')), \
                patch('os.environ', dict(ENV)), \
                patch('frontend.requests.get', side_effect=RequestException):
            self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'jwt')
        patcher = patch('frontend.jwt.decode', return_value=CLAIMS)
        patcher.start()
        self.addCleanup(patcher.stop)

    def backend(self, transactions, contacts=None):
        """Patch the backend calls made through api_call.get"""
        def fake_get(url, **_):
            if '/transactions/' in url:
                if transactions is None:
                    raise RequestException
                return fake_response(transactions)
            if '/balances/' in url:
                return fake_response(12345)
            return fake_response(contacts or [])
        patcher = patch('api_call.get', side_effect=fake_get)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_home_shows_first_page_and_load_more(self):
        """25 transactions: 10 rows and a Load more button"""
        self.backend(make_transactions(25))
        html = self.client.get('/home').get_data(as_text=True)
        self.assertEqual(html.count('class="transaction-type"'), 10)
        self.assertIn('id="load-more-transactions"', html)
        self.assertIn('data-next-offset="10"', html)

    def test_load_more_outside_transaction_table(self):
        """#transaction-table only contains the table (e2e checks its children)"""
        self.backend(make_transactions(25))
        html = self.client.get('/home').get_data(as_text=True)
        between = html[html.index('</table>'):html.index('load-more-container')]
        self.assertIn('</div>', between)

    def test_home_most_recent_first(self):
        """The rows shown are the first (most recent) ones"""
        self.backend(make_transactions(25))
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('$10.00', html)
        self.assertNotIn('$11.00', html)

    def test_home_no_load_more_for_ten_or_fewer(self):
        """Exactly one page: no button"""
        self.backend(make_transactions(10))
        html = self.client.get('/home').get_data(as_text=True)
        self.assertEqual(html.count('class="transaction-type"'), 10)
        self.assertNotIn('load-more-transactions', html)

    def test_home_empty_history(self):
        """No transactions: message, no button"""
        self.backend([])
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('No Transactions Found', html)
        self.assertNotIn('load-more-transactions', html)

    def test_home_history_error(self):
        """History unavailable: error message, no button"""
        self.backend(None)
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('Could Not Load Transactions', html)
        self.assertNotIn('load-more-transactions', html)

    def test_history_next_page(self):
        """offset=10 of 25 returns rows 11-20 and says there is more"""
        self.backend(make_transactions(25))
        data = self.client.get('/history?offset=10').get_json()
        self.assertEqual(data['html'].count('class="transaction-type"'), 10)
        self.assertIn('$11.00', data['html'])
        self.assertIn('$20.00', data['html'])
        self.assertNotIn('$10.00', data['html'])
        self.assertNotIn('$21.00', data['html'])
        self.assertEqual(data['next_offset'], 20)
        self.assertTrue(data['has_more'])

    def test_history_last_page(self):
        """offset=20 of 25 returns the last 5 rows and no more"""
        self.backend(make_transactions(25))
        data = self.client.get('/history?offset=20').get_json()
        self.assertEqual(data['html'].count('class="transaction-type"'), 5)
        self.assertEqual(data['next_offset'], 25)
        self.assertFalse(data['has_more'])

    def test_history_exact_boundary(self):
        """offset=10 of 20: last page is full, nothing more after it"""
        self.backend(make_transactions(20))
        data = self.client.get('/history?offset=10').get_json()
        self.assertEqual(data['next_offset'], 20)
        self.assertFalse(data['has_more'])

    def test_history_offset_past_end(self):
        """An offset beyond the history returns no rows"""
        self.backend(make_transactions(5))
        data = self.client.get('/history?offset=50').get_json()
        self.assertEqual(data['html'].strip(), '')
        self.assertEqual(data['next_offset'], 50)
        self.assertFalse(data['has_more'])

    def test_history_labels_from_contacts(self):
        """Rows loaded later carry the contact labels too"""
        self.backend(make_transactions(12),
                     [{'account_num': OTHER, 'label': 'Friend Alice'}])
        data = self.client.get('/history?offset=10').get_json()
        self.assertIn('Friend Alice', data['html'])

    def test_history_invalid_offset(self):
        """Non-numeric or negative offsets are rejected"""
        self.backend(make_transactions(5))
        self.assertEqual(self.client.get('/history?offset=abc').status_code, 400)
        self.assertEqual(self.client.get('/history?offset=-1').status_code, 400)

    def test_history_backend_down(self):
        """If the history cannot be loaded, 502"""
        self.backend(None)
        self.assertEqual(self.client.get('/history?offset=10').status_code, 502)

    def test_history_requires_login(self):
        """Without a valid token, 401"""
        self.backend(make_transactions(25))
        with patch('frontend.jwt.decode',
                   side_effect=frontend.jwt.exceptions.InvalidTokenError):
            self.assertEqual(self.client.get('/history?offset=10').status_code, 401)
