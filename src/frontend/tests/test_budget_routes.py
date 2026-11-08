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
Tests for the budget parts of the frontend (home page, /budget, /budget/check)
with the backend services mocked
"""

import datetime
import os
import unittest
from unittest.mock import MagicMock, mock_open, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

import frontend

ACCOUNT = '1234567890'
OTHER = '9876543210'
USER = 'alice'

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_PEM = KEY.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo).decode()

BASE_ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'HISTORY_API_ADDR': 'history:8080',
    'BALANCES_API_ADDR': 'balances:8080',
    'CONTACTS_API_ADDR': 'contacts:8080',
    'LOCAL_ROUTING_NUM': '883745000',
}


def make_token():
    """A login token signed with the test key"""
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {'user': USER, 'acct': ACCOUNT, 'name': 'Alice',
              'iat': now, 'exp': now + datetime.timedelta(hours=1)}
    return jwt.encode(claims, KEY, algorithm='RS256')


def this_month(day=1):
    """A transaction timestamp in the current month"""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.replace(day=day).strftime('%Y-%m-%dT%H:%M:%S.%f%z')


def spent(amount):
    """A payment sent by the test user this month"""
    return {'fromAccountNum': ACCOUNT, 'toAccountNum': OTHER,
            'fromRoutingNum': '883745000', 'toRoutingNum': '883745000',
            'amount': amount, 'timestamp': this_month(),
            'accountLabel': None}


def reply(body=None, status=200):
    """A mocked requests response"""
    resp = MagicMock()
    resp.status_code = status
    resp.ok = status < 400
    resp.__bool__.return_value = status < 400
    resp.json.return_value = body
    resp.text = ''
    if status >= 400:
        resp.raise_for_status.side_effect = HTTPError(str(status))
    return resp


class FakeBackend:
    """Routes the frontend's requests to canned replies by URL"""

    def __init__(self, budget=None, history=None, budgets_down=False,
                 put_status=200):
        self.budget = budget
        self.history = history if history is not None else []
        self.budgets_down = budgets_down
        self.put_status = put_status
        self.calls = []

    def get(self, url=None, **kwargs):
        """Mocked requests.get"""
        self.calls.append(('GET', url))
        if '/budget/' in url:
            if self.budgets_down:
                raise RequestsConnectionError
            return reply({'limit_cents': self.budget})
        if '/balances/' in url:
            return reply(100000)
        if '/transactions/' in url:
            return reply(self.history)
        if '/contacts/' in url:
            return reply([])
        raise RequestsConnectionError

    def put(self, url=None, **kwargs):
        """Mocked requests.put"""
        self.calls.append(('PUT', url, kwargs.get('json')))
        if self.budgets_down:
            raise RequestsConnectionError
        return reply(kwargs.get('json'), self.put_status)

    def delete(self, url=None, **kwargs):
        """Mocked requests.delete"""
        self.calls.append(('DELETE', url))
        if self.budgets_down:
            raise RequestsConnectionError
        return reply(None, 204)


class BudgetRoutesTestCase(unittest.TestCase):
    """Base: an app with a signed-in client and a fake backend"""

    def setUp(self):
        env = dict(BASE_ENV, BUDGETS_API_ADDR='budgets:8080')
        self.start(env)

    def start(self, env, **backend_args):
        """Create the app with env and the fake backend"""
        self.backend = FakeBackend(**backend_args)
        patches = [
            patch('os.environ', env),
            patch('frontend.open', mock_open(read_data=PUBLIC_PEM)),
            patch('requests.get', self.backend.get),
            patch('requests.put', self.backend.put),
            patch('requests.delete', self.backend.delete),
            patch('api_call.get', self.backend.get),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = frontend.create_app()
        self.client = self.app.test_client()
        self.client.set_cookie('token', make_token())

    def configure(self, **backend_args):
        """Change the canned replies"""
        for name, value in backend_args.items():
            setattr(self.backend, name, value)


class TestHomeBudget(BudgetRoutesTestCase):
    """Tests the budget section of the home page"""

    def test_usage_shown_with_spent_remaining_and_percent(self):
        self.configure(budget=20000, history=[spent(5000), spent(2500)])
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('id="budget-progress"', html)
        self.assertIn('$75.00</span> spent of', html)
        self.assertIn('$200.00</span> this month', html)
        self.assertIn('$125.00</span> remaining', html)
        self.assertIn('37%</span> used', html)
        self.assertIn('data-budget-check="true"', html)

    def test_over_budget_bar_is_full(self):
        self.configure(budget=1000, history=[spent(2500)])
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('width: 100%', html)
        self.assertIn('250%</span> used', html)
        self.assertIn('$0.00</span> remaining', html)

    def test_no_budget_shows_form_without_usage(self):
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('id="budget-form"', html)
        self.assertIn('id="budget-empty"', html)
        self.assertNotIn('id="budget-progress"', html)
        self.assertNotIn('data-budget-check', html)

    def test_budget_service_down_home_still_works(self):
        self.configure(budgets_down=True, history=[spent(100)])
        resp = self.client.get('/home')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertNotIn('budget-section', html)
        self.assertIn('id="current-balance"', html)
        self.assertIn('id="transaction-list"', html)
        self.assertNotIn('data-budget-check', html)

    def test_no_budgets_address_home_still_works(self):
        env = dict(BASE_ENV)
        self.start(env)
        self.assertIsNone(self.app.config['BUDGETS_URI'])
        resp = self.client.get('/home')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('budget-section', resp.get_data(as_text=True))
        self.assertFalse(any('/budget' in c[1] for c in self.backend.calls))

    def test_history_unavailable_shows_limit_only(self):
        self.configure(budget=20000)
        with patch('api_call.get', side_effect=RequestsConnectionError):
            html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('id="budget-section"', html)
        self.assertNotIn('id="budget-progress"', html)
        self.assertIn('Spending is unavailable', html)


class TestSetBudget(BudgetRoutesTestCase):
    """Tests setting and clearing the budget"""

    def test_requires_login(self):
        self.client.delete_cookie('token')
        resp = self.client.post('/budget', data={'limit': '100'})
        self.assertEqual(resp.status_code, 401)

    def test_set_limit_sends_whole_cents(self):
        resp = self.client.post('/budget', data={'limit': '500.50'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('Budget+saved', resp.headers['Location'])
        self.assertIn(('PUT', 'http://budgets:8080/budget/alice',
                       {'limit_cents': 50050}), self.backend.calls)

    def test_invalid_limit_is_not_sent(self):
        for value in ['', 'abc', '0', '-1', '1.234']:
            with self.subTest(value=value):
                resp = self.client.post('/budget', data={'limit': value})
                self.assertIn('Budget+not+saved', resp.headers['Location'])
        self.assertFalse([c for c in self.backend.calls if c[0] == 'PUT'])

    def test_clear_limit(self):
        resp = self.client.post('/budget', data={'action': 'clear'})
        self.assertIn('Budget+cleared', resp.headers['Location'])
        self.assertIn(('DELETE', 'http://budgets:8080/budget/alice'),
                      self.backend.calls)

    def test_service_down_redirects_with_message(self):
        self.configure(budgets_down=True)
        resp = self.client.post('/budget', data={'limit': '100'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('Could+not+save', resp.headers['Location'])
        resp = self.client.post('/budget', data={'action': 'clear'})
        self.assertIn('Could+not+clear', resp.headers['Location'])

    def test_service_rejects_limit(self):
        self.configure(put_status=400)
        resp = self.client.post('/budget', data={'limit': '100'})
        self.assertIn('Could+not+save', resp.headers['Location'])


class TestBudgetCheck(BudgetRoutesTestCase):
    """Tests the warning decision before a payment"""

    def check(self, amount):
        """Ask whether a payment of amount dollars would exceed the budget"""
        resp = self.client.get('/budget/check', query_string={'amount': amount})
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()

    def test_requires_login(self):
        self.client.delete_cookie('token')
        self.assertEqual(self.client.get('/budget/check?amount=1').status_code, 401)

    def test_warns_when_payment_would_exceed_limit(self):
        self.configure(budget=10000, history=[spent(7000)])
        result = self.check('30.01')
        self.assertTrue(result['exceeds'])
        self.assertEqual(result['limit_cents'], 10000)
        self.assertEqual(result['spent_cents'], 7000)
        self.assertEqual(result['after_cents'], 10001)

    def test_no_warning_up_to_the_limit(self):
        self.configure(budget=10000, history=[spent(7000)])
        self.assertFalse(self.check('30.00')['exceeds'])

    def test_no_warning_without_budget(self):
        self.configure(history=[spent(7000)])
        self.assertEqual(self.check('99999'), {'exceeds': False})

    def test_no_warning_when_budget_service_down(self):
        self.configure(budgets_down=True, budget=10000)
        self.assertEqual(self.check('99999'), {'exceeds': False})

    def test_no_warning_when_history_unavailable(self):
        self.configure(budget=10000)
        with patch('api_call.get', side_effect=RequestsConnectionError):
            self.assertEqual(self.check('99999'), {'exceeds': False})

    def test_no_warning_for_unreadable_amount(self):
        self.configure(budget=100)
        self.assertEqual(self.check('abc'), {'exceeds': False})
        self.assertEqual(self.check(''), {'exceeds': False})

    def test_no_warning_without_budgets_address(self):
        self.start(dict(BASE_ENV), budget=100)
        self.assertEqual(self.check('50'), {'exceeds': False})


if __name__ == '__main__':
    unittest.main()
