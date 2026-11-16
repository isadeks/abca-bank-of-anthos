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

"""Tests for spending categories: payment form, history and home breakdown"""

import json
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
TOKEN_DATA = {'user': 'testuser', 'acct': '1234567890', 'name': 'Test'}
HISTORY = [
    {'fromAccountNum': '1234567890', 'toAccountNum': '9999999999',
     'amount': 1500, 'timestamp': '2026-01-05T10:00:00.000+0000',
     'category': 'Groceries'},
    {'fromAccountNum': '1234567890', 'toAccountNum': '8888888888',
     'amount': 700, 'timestamp': '2026-01-04T10:00:00.000+0000'},
]
SPENDING = {'Groceries': 1500, 'Rent': 0, 'Transport': 750,
            'Eating out': 0, 'Other': 0}


def fake_call(urls):
    """Returns a make_call replacement that records requested urls"""
    def make_call(self):
        url = self.api_request.url
        urls.append(url)
        resp = MagicMock()
        if url.endswith('/spending'):
            resp.json.return_value = SPENDING
        elif '/transactions/' in url:
            resp.json.return_value = HISTORY
        elif 'balances' in url:
            resp.json.return_value = 5000
        else:
            return None
        return resp
    return make_call


class TestCategories(unittest.TestCase):
    """Category handling in the frontend"""

    def setUp(self):
        self.urls = []
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.ApiCall.make_call', fake_call(self.urls)),
            patch('frontend.sleep'),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.post_patch = patch('frontend.requests.post')
        self.post = self.post_patch.start()
        self.addCleanup(self.post_patch.stop)
        self.post.return_value.status_code = 201
        self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'abc')

    def sent_category(self, **form):
        """Submit a payment and return the category sent to the ledger"""
        data = {'account_num': '9999999999', 'amount': '10', 'uuid': 'u1'}
        data.update(form)
        self.client.post('/payment', data=data)
        sent = json.loads(self.post.call_args.kwargs['data'])
        return sent.get('category', 'Other')

    def test_payment_sends_chosen_category(self):
        """the chosen category is passed to the ledger writer"""
        self.assertEqual(self.sent_category(category='Rent'), 'Rent')

    def test_payment_defaults_to_other(self):
        """no category means Other"""
        self.assertEqual(self.sent_category(), 'Other')

    def test_payment_unknown_category_is_other(self):
        """an unknown category is not forwarded"""
        self.assertEqual(self.sent_category(category='Yachts'), 'Other')

    def test_home_shows_categories_and_spending(self):
        """history rows show categories (missing = Other), bars are shown"""
        body = self.client.get('/home').get_data(as_text=True)
        self.assertIn('id="payment-category"', body)
        self.assertIn('<td class="transaction-category">Groceries</td>', body)
        self.assertIn('<td class="transaction-category">Other</td>', body)
        self.assertIn('id="spending-breakdown"', body)
        self.assertIn('data-category="Transport"', body)
        self.assertIn('width: 50%', body)
        self.assertIn('width: 100%', body)

    def test_home_filters_history_by_category(self):
        """the category query parameter is passed to transaction history"""
        self.client.get('/home?category=Eating%20out')
        self.assertTrue(any(u.endswith('/1234567890?category=Eating%20out')
                            for u in self.urls))

    def test_home_ignores_unknown_filter(self):
        """an unknown filter value is not passed on"""
        self.client.get('/home?category=Yachts')
        self.assertFalse(any('category=' in u for u in self.urls))

    def test_spending_bars_unavailable(self):
        """no spending data gives no bars"""
        app = frontend.create_app()
        self.assertIsNotNone(app)
        with patch('frontend.ApiCall.make_call', return_value=None):
            body = self.client.get('/home').get_data(as_text=True)
        self.assertIn('Spending is currently unavailable', body)
