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
Opening a savings account: the home page option and the /savings handler.
"""

from unittest.mock import MagicMock, patch

from requests.exceptions import RequestException

import frontend
from test_payment_deposit_handlers import (
    ACCOUNT_ID, HandlerTestCase, backend_response)


class TestSavingsAccount(HandlerTestCase):
    """Users can open a savings account from the home page"""

    def savings_calls(self):
        """The mocked posts that went to userservice's savings endpoint"""
        uri = self.app.config['USERSERVICE_URI'] + '/testuser/savings'
        return [c for c in self.post.call_args_list if c.kwargs['url'] == uri]

    def home_with_savings(self, savings_response):
        """Render the home page with the given response for the savings lookup"""
        def make_call(call):
            if call.display_name == frontend.SAVINGS_NAME:
                return savings_response
            return None
        with patch('frontend.ApiCall.make_call', new=make_call):
            return self.client.get('/home')

    def test_home_offers_to_open_a_savings_account(self):
        """without a savings account the home page shows the option"""
        html = self.home_with_savings(None).get_data(as_text=True)
        self.assertIn('id="open-savings-button"', html)
        self.assertIn('action="/savings"', html)
        self.assertNotIn('id="savings-account-number"', html)

    def test_home_shows_the_savings_account_number(self):
        """with a savings account the home page shows its number, not the option"""
        resp = MagicMock()
        resp.json.return_value = {'accountid': '4242424242'}
        html = self.home_with_savings(resp).get_data(as_text=True)
        self.assertIn('id="savings-account-number">4242424242<', html)
        self.assertNotIn('id="open-savings-button"', html)

    def test_open_savings_account_posts_to_userservice_and_redirects(self):
        """a signed in user opens an account for their own username"""
        resp = self.client.post('/savings')
        self.assertEqual(resp.status_code, 303)
        self.assertIn('msg=Savings+account+opened', resp.headers['Location'])
        self.assertEqual(len(self.savings_calls()), 1)
        self.assertNotIn(ACCOUNT_ID, self.savings_calls()[0].kwargs['url'])

    def test_open_savings_account_without_token_is_unauthorized(self):
        """no token cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        resp = self.client.post('/savings')
        self.assertEqual(resp.status_code, 401)
        self.post.assert_not_called()

    def test_open_savings_account_twice_shows_an_error(self):
        """a 409 from userservice is reported on the home page"""
        self.post.return_value = backend_response(409, 'already')
        resp = self.client.post('/savings')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('You already have a savings account',
                      resp.get_data(as_text=True))

    def test_open_savings_account_backend_error_shows_an_error(self):
        """a failing userservice is reported as a bad gateway"""
        self.post.return_value = backend_response(500, 'boom')
        resp = self.client.post('/savings')
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Could not open a savings account',
                      resp.get_data(as_text=True))

    def test_open_savings_account_unreachable_userservice(self):
        """a connection error is reported as a bad gateway"""
        self.post.side_effect = RequestException
        resp = self.client.post('/savings')
        self.assertEqual(resp.status_code, 502)
