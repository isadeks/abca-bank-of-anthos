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
Tests for the frontend's "split a bill between contacts" action
"""

import json
import os
import time
import unittest
import uuid
from unittest.mock import MagicMock, mock_open, patch

import jwt
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import frontend

SELF_ACCOUNT = '1000000000'
CONTACTS = [
    {'label': 'Alice', 'account_num': '1111111111', 'routing_num': '883745000',
     'is_external': False},
    {'label': 'Bob', 'account_num': '2222222222', 'routing_num': '883745000',
     'is_external': False},
    {'label': 'Carol', 'account_num': '3333333333', 'routing_num': '883745000',
     'is_external': False},
    {'label': 'Dave', 'account_num': '4444444444', 'routing_num': '883745000',
     'is_external': False},
    {'label': 'Erin', 'account_num': '5555555555', 'routing_num': '883745000',
     'is_external': False},
    {'label': 'Bank', 'account_num': '9999999999', 'routing_num': '123456789',
     'is_external': True},
]

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
    'TRANSACTIONS_API_ADDR': 'ledgerwriter:8080',
    'CONTACTS_API_ADDR': 'contacts:8080',
}

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_PEM = KEY.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def make_token():
    """A signed token for the demo user"""
    now = int(time.time())
    return jwt.encode({'user': 'testuser', 'acct': SELF_ACCOUNT, 'name': 'Test',
                       'iat': now, 'exp': now + 3600}, KEY, algorithm='RS256')


def fake_response(status=200, payload=None):
    """A stand-in for requests.Response"""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.text = 'rejected'
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError()
    return resp


class TestSplitAmount(unittest.TestCase):
    """Tests the share arithmetic"""

    def test_even_split(self):
        """An evenly divisible total gives equal shares"""
        self.assertEqual(frontend.split_amount(3000, 3), [1000, 1000, 1000])

    def test_last_share_takes_the_rounding(self):
        """$100.00 between 3 is 33.33, 33.33, 33.34"""
        self.assertEqual(frontend.split_amount(10000, 3), [3333, 3333, 3334])

    def test_shares_always_add_up(self):
        """For every size and a range of totals the shares sum to the total"""
        for count in (2, 3, 4):
            for total in range(count, 500):
                shares = frontend.split_amount(total, count)
                self.assertEqual(len(shares), count)
                self.assertEqual(sum(shares), total)
                self.assertTrue(all(share >= 1 for share in shares))
                self.assertTrue(max(shares) - min(shares) < count)


class TestSplitRoutes(unittest.TestCase):
    """Tests the /split/preview and /split routes"""

    def setUp(self):
        with patch.dict(os.environ, {}), \
                patch('frontend.open', mock_open(read_data=PUBLIC_PEM)), \
                patch('os.environ', dict(ENV)), \
                patch('frontend.requests.get', side_effect=requests.RequestException):
            app = frontend.create_app()
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.client.set_cookie('token', make_token())
        self.request_uuid = str(uuid.uuid4())

    def form(self, accounts, amount='100.00'):
        """Form data as the modal submits it"""
        return {'contacts': accounts, 'amount': amount, 'uuid': self.request_uuid}

    def preview(self, accounts, amount='100.00', contacts=None):
        """POST /split/preview with the contacts service mocked"""
        resp = fake_response(200, CONTACTS if contacts is None else contacts)
        with patch('frontend.requests.get', return_value=resp):
            return self.client.post('/split/preview', data=self.form(accounts, amount))

    def split(self, accounts, amount='100.00', post=None):
        """POST /split with the contacts service and ledgerwriter mocked"""
        post = post or MagicMock(return_value=fake_response(201))
        with patch('frontend.requests.get', return_value=fake_response(200, CONTACTS)), \
                patch('frontend.requests.post', post), \
                patch('frontend.sleep'):
            resp = self.client.post('/split', data=self.form(accounts, amount))
        return resp, post

    def test_preview_lists_shares_and_total(self):
        """The summary has one share per contact, the last absorbing the rounding"""
        resp = self.preview(['1111111111', '2222222222', '3333333333'])
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual([s['amount'] for s in body['shares']], [3333, 3333, 3334])
        self.assertEqual([s['label'] for s in body['shares']], ['Alice', 'Bob', 'Carol'])
        self.assertEqual(body['total'], 10000)

    def test_preview_requires_login(self):
        """No token, no preview"""
        self.client.delete_cookie('token')
        resp = self.client.post('/split/preview', data=self.form(['1111111111', '2222222222']))
        self.assertEqual(resp.status_code, 401)

    def test_preview_rejects_too_few_or_too_many_contacts(self):
        """Only 2 to 4 contacts can share a bill"""
        accounts = [c['account_num'] for c in CONTACTS[:5]]
        for picked in (accounts[:1], accounts[:5], []):
            resp = self.preview(picked)
            self.assertEqual(resp.status_code, 400, picked)
            self.assertIn('2 to 4', resp.get_json()['error'])
        for picked in (accounts[:2], accounts[:4]):
            self.assertEqual(self.preview(picked).status_code, 200)

    def test_duplicate_contacts_count_once(self):
        """Picking the same contact twice does not make it two contacts"""
        resp = self.preview(['1111111111', '1111111111'])
        self.assertEqual(resp.status_code, 400)

    def test_preview_rejects_bad_amounts(self):
        """Zero, negative, text, sub-cent and non-finite totals are refused"""
        for amount in ('0', '-5', 'abc', '10.005', 'Infinity', 'NaN', '0.01', ''):
            resp = self.preview(['1111111111', '2222222222'], amount)
            self.assertEqual(resp.status_code, 400, amount)

    def test_preview_rejects_unknown_and_external_contacts(self):
        """Only the user's own local contacts can receive a share"""
        for other in ('7777777777', '9999999999'):
            resp = self.preview(['1111111111', other])
            self.assertEqual(resp.status_code, 400, other)
            self.assertIn('unknown contact', resp.get_json()['error'])

    def test_preview_rejects_self(self):
        """You cannot split a bill with yourself"""
        contacts = CONTACTS + [{'label': 'Me', 'account_num': SELF_ACCOUNT,
                                'routing_num': '883745000', 'is_external': False}]
        resp = self.preview(['1111111111', SELF_ACCOUNT], contacts=contacts)
        self.assertEqual(resp.status_code, 400)

    def test_preview_contacts_service_down(self):
        """A failing contacts service is a gateway error, not a crash"""
        with patch('frontend.requests.get', side_effect=requests.RequestException):
            resp = self.client.post('/split/preview',
                                    data=self.form(['1111111111', '2222222222']))
        self.assertEqual(resp.status_code, 502)

    def test_split_sends_each_contact_its_share(self):
        """One payment per contact, summing to the total exactly"""
        resp, post = self.split(['1111111111', '2222222222', '3333333333'])
        self.assertEqual(resp.status_code, 303)
        self.assertIn('Bill+split+between+3+contacts', resp.headers['Location'])
        sent = [json.loads(call.kwargs['data']) for call in post.call_args_list]
        self.assertEqual([t['toAccountNum'] for t in sent],
                         ['1111111111', '2222222222', '3333333333'])
        self.assertEqual([t['amount'] for t in sent], [3333, 3333, 3334])
        self.assertEqual(sum(t['amount'] for t in sent), 10000)
        for transaction in sent:
            self.assertEqual(transaction['fromAccountNum'], SELF_ACCOUNT)
        # each payment has its own, stable uuid
        self.assertEqual(len({t['uuid'] for t in sent}), 3)
        _, again = self.split(['1111111111', '2222222222', '3333333333'])
        self.assertEqual([json.loads(c.kwargs['data'])['uuid'] for c in again.call_args_list],
                         [t['uuid'] for t in sent])

    def test_split_requires_login(self):
        """No token, no payments"""
        self.client.delete_cookie('token')
        resp, post = self.split(['1111111111', '2222222222'])
        self.assertEqual(resp.status_code, 401)
        post.assert_not_called()

    def test_invalid_split_sends_nothing(self):
        """Validation failures redirect home with a message and pay nobody"""
        resp, post = self.split(['1111111111'])
        self.assertEqual(resp.status_code, 303)
        self.assertIn('Split+failed', resp.headers['Location'])
        post.assert_not_called()

    def test_split_stops_when_a_payment_is_rejected(self):
        """A rejected share is reported with how many contacts were already paid"""
        post = MagicMock(side_effect=[fake_response(201), fake_response(400)])
        resp, post = self.split(['1111111111', '2222222222', '3333333333'], post=post)
        self.assertEqual(post.call_count, 2)
        self.assertIn('Split+failed+after+paying+1+of+3+contacts',
                      resp.headers['Location'])


if __name__ == '__main__':
    unittest.main()
