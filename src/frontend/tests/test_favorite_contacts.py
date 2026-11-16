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

"""Unit tests for favourite contacts on the payment form."""

import json
import unittest
from unittest.mock import MagicMock, patch, mock_open

import requests

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
}
TOKEN_DATA = {'user': 'testuser', 'acct': '1234567890', 'name': 'Test'}
CONTACTS = [
    {'label': 'Alice', 'account_num': '1111111111', 'routing_num': '883745000',
     'is_external': False, 'is_favorite': False},
    {'label': 'Bob', 'account_num': '2222222222', 'routing_num': '883745000',
     'is_external': False, 'is_favorite': True},
    {'label': 'Carol', 'account_num': '3333333333', 'routing_num': '883745000',
     'is_external': False},
]


def fake_call(contacts):
    """Replacement for ApiCall.make_call returning contacts for the contacts call"""
    def make_call(self):
        resp = MagicMock()
        if self.display_name == 'contacts':
            resp.json.return_value = contacts
        elif self.display_name == 'transaction_list':
            resp.json.return_value = []
        else:
            resp.json.return_value = 100
        return resp
    return make_call


class FavoriteTestCase(unittest.TestCase):
    """Builds the app with every backend call mocked"""

    def setUp(self):
        for started in [
                patch('os.environ', dict(ENV)),
                patch('frontend.open', mock_open(read_data='foo')),
                patch('frontend.jwt.decode', return_value=TOKEN_DATA)]:
            started.start()
            self.addCleanup(started.stop)
        self.put = patch('frontend.requests.put').start()
        self.addCleanup(patch.stopall)
        self.app = frontend.create_app()
        self.client = self.app.test_client()
        self.client.set_cookie('token', 'abc')

    def home(self, contacts):
        """Render /home with the given contacts"""
        with patch('frontend.ApiCall.make_call', fake_call(contacts)):
            return self.client.get('/home').get_data(as_text=True)


class TestPaymentFormOrder(FavoriteTestCase):
    """Favourites are listed first, with a star"""

    def test_favourites_first_with_star(self):
        """the starred contact precedes the others and carries a star"""
        page = self.home(CONTACTS)
        bob = page.index('★ Bob - 2222222222')
        self.assertLess(bob, page.index('Alice - 1111111111'))
        self.assertLess(bob, page.index('Carol - 3333333333'))
        self.assertEqual(page.count('★ Alice'), 0)

    def test_other_order_is_kept(self):
        """non-favourites keep the service's order"""
        page = self.home(CONTACTS)
        self.assertLess(page.index('Alice - 1111111111'),
                        page.index('Carol - 3333333333'))


class TestFavoriteRoute(FavoriteTestCase):
    """POST /favorite forwards to the contacts service"""

    def test_requires_token(self):
        """no cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        resp = self.client.post('/favorite',
                                data={'label': 'Bob', 'is_favorite': 'true'})
        self.assertEqual(resp.status_code, 401)
        self.put.assert_not_called()

    def test_invalid_form_is_rejected(self):
        """missing label or bad flag gives 400"""
        resp = self.client.post('/favorite', data={'is_favorite': 'true'})
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post('/favorite',
                                data={'label': 'Bob', 'is_favorite': 'maybe'})
        self.assertEqual(resp.status_code, 400)
        self.put.assert_not_called()

    def test_stars_contact(self):
        """a valid request puts the flag to the contacts service"""
        resp = self.client.post('/favorite',
                                data={'label': 'Bob', 'is_favorite': 'true'})
        self.assertEqual(resp.status_code, 204)
        call = self.put.call_args
        self.assertEqual(call.kwargs['url'],
                         self.app.config['CONTACTS_URI'] + '/testuser/favorite')
        self.assertEqual(json.loads(call.kwargs['data']),
                         {'label': 'Bob', 'is_favorite': True})

    def test_unstars_contact(self):
        """is_favorite=false is sent as a boolean false"""
        self.client.post('/favorite',
                         data={'label': 'Bob', 'is_favorite': 'false'})
        self.assertFalse(json.loads(self.put.call_args.kwargs['data'])['is_favorite'])

    def test_backend_error_status_is_passed_on(self):
        """a 404 from contacts is returned"""
        resp404 = MagicMock(status_code=404, text='contact not found')
        resp404.raise_for_status.side_effect = requests.exceptions.HTTPError()
        self.put.return_value = resp404
        resp = self.client.post('/favorite',
                                data={'label': 'Zed', 'is_favorite': 'true'})
        self.assertEqual(resp.status_code, 404)

    def test_backend_down_gives_502(self):
        """a connection failure gives 502"""
        self.put.side_effect = requests.exceptions.ConnectionError
        resp = self.client.post('/favorite',
                                data={'label': 'Bob', 'is_favorite': 'true'})
        self.assertEqual(resp.status_code, 502)


if __name__ == '__main__':
    unittest.main()
