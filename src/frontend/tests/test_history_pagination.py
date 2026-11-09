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
Tests that the home page shows only the 10 most recent transactions and that
/history serves the following pages.
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
}
ACCOUNT = '1234567890'
TOKEN_DATA = {'user': 'testuser', 'acct': ACCOUNT, 'name': 'Test'}
CONTACTS = [{'account_num': '1000000001', 'label': 'Alice',
             'is_external': False, 'routing_num': '883745000'}]


def make_transactions(count):
    """Newest first, like transactionhistory: amount encodes the position"""
    return [{'fromAccountNum': '1000000001', 'toAccountNum': ACCOUNT,
             'amount': (i + 1) * 100, 'timestamp': '2026-01-01T10:00:00.000000+0000'}
            for i in range(count)]


def fake_call(transactions):
    """Stand in for ApiCall.make_call, answering by the call's name"""
    def make_call(self):
        resp = MagicMock()
        if self.display_name == frontend.TRANSACTION_LIST_NAME:
            resp.json.return_value = transactions
        elif self.display_name == frontend.CONTACTS_NAME:
            resp.json.return_value = CONTACTS
        else:
            resp.json.return_value = 100000
        return resp
    return make_call


class TestHistoryPagination(unittest.TestCase):
    """Home page and /history return transactions ten at a time"""

    def client_with(self, count, authenticated=True):
        """A test client whose backend holds `count` transactions"""
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.ApiCall.make_call', fake_call(make_transactions(count))),
        ]
        if not authenticated:
            patches[2] = patch('frontend.jwt.decode',
                               side_effect=frontend.jwt.exceptions.InvalidTokenError)
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        client = frontend.create_app().test_client()
        client.set_cookie('token', 'abc')
        return client

    def test_home_shows_ten_and_load_more(self):
        """25 transactions: 10 rows and a Load more button"""
        body = self.client_with(25).get('/home').get_data(as_text=True)
        self.assertEqual(body.count('class="transaction-amount '), 10)
        self.assertIn('id="load-more-transactions"', body)
        self.assertIn('data-offset="10"', body)

    def test_home_short_history_has_no_load_more(self):
        """10 or fewer transactions: no button"""
        body = self.client_with(10).get('/home').get_data(as_text=True)
        self.assertEqual(body.count('class="transaction-amount '), 10)
        self.assertNotIn('load-more-transactions', body)

    def test_home_empty_history(self):
        """no transactions: the empty message, no button"""
        body = self.client_with(0).get('/home').get_data(as_text=True)
        self.assertIn('No Transactions Found', body)
        self.assertNotIn('load-more-transactions', body)

    def test_history_returns_next_page(self):
        """offset 10 of 25 returns rows 11-20 and says more remain"""
        data = self.client_with(25).get('/history?offset=10').get_json()
        self.assertEqual(data['html'].count('<tr>'), 10)
        self.assertIn('$11.00', data['html'])
        self.assertNotIn('$10.00', data['html'])
        self.assertIn('Alice', data['html'])
        self.assertEqual(data['next_offset'], 20)
        self.assertTrue(data['has_more'])

    def test_history_last_page(self):
        """offset 20 of 25 returns the last 5 rows and no more"""
        data = self.client_with(25).get('/history?offset=20').get_json()
        self.assertEqual(data['html'].count('<tr>'), 5)
        self.assertEqual(data['next_offset'], 25)
        self.assertFalse(data['has_more'])

    def test_history_offset_past_end(self):
        """an offset past the end returns nothing"""
        data = self.client_with(5).get('/history?offset=50').get_json()
        self.assertEqual(data['html'].strip(), '')
        self.assertFalse(data['has_more'])

    def test_history_bad_offset(self):
        """a non numeric or negative offset is a 400"""
        client = self.client_with(25)
        self.assertEqual(client.get('/history?offset=abc').status_code, 400)
        self.assertEqual(client.get('/history?offset=-1').status_code, 400)

    def test_history_requires_login(self):
        """an invalid token is a 401"""
        client = self.client_with(25, authenticated=False)
        self.assertEqual(client.get('/history?offset=10').status_code, 401)


if __name__ == '__main__':
    unittest.main()
