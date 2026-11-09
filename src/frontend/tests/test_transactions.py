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
Tests that failed payments and deposits answer with a failure status and
show an error message, while the happy path still redirects home.
"""

import os
import unittest
from unittest.mock import MagicMock, patch, mock_open

import requests
from requests.exceptions import RequestException

import frontend

LOCAL_ROUTING = '883745000'
ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': LOCAL_ROUTING,
}
TOKEN_DATA = {'user': 'testuser', 'acct': '1234567890', 'name': 'Test'}


def backend_response(status_code, text=''):
    """A fake ledgerwriter response"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(text)
    return resp


class TestFailedTransactions(unittest.TestCase):
    """Payment and deposit failures are not reported as success"""

    def setUp(self):
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.requests.get', side_effect=RequestException),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.ApiCall.make_call', return_value=None),
            patch('frontend.sleep'),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.post_patch = patch('frontend.requests.post')
        self.post = self.post_patch.start()
        self.addCleanup(self.post_patch.stop)
        self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'abc')

    def payment(self, **overrides):
        """Submit a payment form"""
        form = {'account_num': '9999999999', 'amount': '10', 'uuid': 'u1'}
        form.update(overrides)
        return self.client.post('/payment', data=form)

    def deposit(self, **overrides):
        """Submit a deposit form to a new external account"""
        form = {'account': 'add', 'external_account_num': '1111111111',
                'external_routing_num': '123456789', 'amount': '10',
                'uuid': 'u2'}
        form.update(overrides)
        return self.client.post('/deposit', data=form)

    def test_payment_success_redirects_home(self):
        """the happy path is unchanged: 303 to the home page"""
        self.post.return_value = backend_response(201)
        resp = self.payment()
        self.assertEqual(resp.status_code, 303)
        self.assertIn('msg=Payment+successful', resp.headers['Location'])

    def test_deposit_success_redirects_home(self):
        """the happy path is unchanged: 303 to the home page"""
        self.post.return_value = backend_response(201)
        resp = self.deposit()
        self.assertEqual(resp.status_code, 303)
        self.assertIn('msg=Deposit+successful', resp.headers['Location'])

    def test_payment_invalid_amount_is_rejected(self):
        """a non numeric amount gives 400 and an error naming the input"""
        resp = self.payment(amount='abc')
        self.assertEqual(resp.status_code, 400)
        body = resp.get_data(as_text=True)
        self.assertIn('Payment failed: abc is not a valid number', body)
        self.assertIn('id="alert-message"', body)
        self.assertIn('text-danger', body)
        self.post.assert_not_called()

    def test_payment_rejected_by_ledger(self):
        """a 4xx from ledgerwriter gives 400 with its reason"""
        self.post.return_value = backend_response(400, 'insufficient balance')
        resp = self.payment()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Payment failed: insufficient balance',
                      resp.get_data(as_text=True))

    def test_payment_backend_server_error(self):
        """a 5xx from ledgerwriter gives 502"""
        self.post.return_value = backend_response(500, 'boom')
        resp = self.payment()
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Payment failed', resp.get_data(as_text=True))

    def test_payment_backend_unreachable(self):
        """a connection error gives 502 and an error message"""
        self.post.side_effect = requests.exceptions.ConnectionError
        resp = self.payment()
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Payment failed', resp.get_data(as_text=True))

    def test_deposit_local_routing_number_is_rejected(self):
        """the local routing number gives 400 with the reason"""
        resp = self.deposit(external_routing_num=LOCAL_ROUTING)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Deposit failed: invalid routing number',
                      resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_deposit_invalid_amount_is_rejected(self):
        """a non numeric amount gives 400"""
        self.post.return_value = backend_response(201)
        resp = self.deposit(amount='ten')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Deposit failed: ten is not a valid number',
                      resp.get_data(as_text=True))

    def test_deposit_backend_unreachable(self):
        """a connection error gives 502 and an error message"""
        self.post.side_effect = requests.exceptions.ConnectionError
        resp = self.deposit(account='{"account_num": "1", "routing_num": "2"}')
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Deposit failed', resp.get_data(as_text=True))

    def test_deposit_backend_server_error(self):
        """a 5xx from ledgerwriter gives 502"""
        self.post.return_value = backend_response(503, 'down')
        resp = self.deposit(account='{"account_num": "1", "routing_num": "2"}')
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Deposit failed: down', resp.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
