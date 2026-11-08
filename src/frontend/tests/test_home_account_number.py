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
Tests for the account number and its copy button on the home page
"""

import os
import unittest
from unittest.mock import MagicMock, patch, mock_open

from requests.exceptions import RequestException

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
}
ACCOUNT_ID = '1234567890'


class TestHomeAccountNumber(unittest.TestCase):
    """The home page shows the account number with a Copy button"""

    def setUp(self):
        with patch('frontend.open', mock_open(read_data='foo')), \
                patch('os.environ', dict(ENV)), \
                patch('frontend.requests.get', side_effect=RequestException):
            app = frontend.create_app()
        self.client = app.test_client()
        self.client.set_cookie('token', 'fake-token')

    def _get_home(self):
        claims = {'acct': ACCOUNT_ID, 'user': 'testuser', 'name': 'Test User'}
        with patch('frontend.jwt.decode', return_value=claims), \
                patch('api_call.get', side_effect=RequestException):
            return self.client.get('/home')

    def test_home_shows_account_number_next_to_balance(self):
        """account number is rendered in the balance card"""
        html = self._get_home().get_data(as_text=True)
        balance_card = html.split('id="current-balance"')[1].split('Deposit Funds')[0]
        self.assertIn(f'id="account-number">{ACCOUNT_ID}</span>', balance_card)

    def test_home_has_copy_button_for_account_number(self):
        """a Copy button carries the account number to copy"""
        html = self._get_home().get_data(as_text=True)
        self.assertIn('id="copy-account-number"', html)
        self.assertIn(f'data-account-number="{ACCOUNT_ID}"', html)
        self.assertIn('>Copy</button>', html)

    def test_home_loads_copy_script(self):
        """the page script that wires up the Copy button is included"""
        html = self._get_home().get_data(as_text=True)
        self.assertIn('static/scripts/index.js', html)
        with open(os.path.join(os.path.dirname(frontend.__file__),
                               'static', 'scripts', 'index.js')) as script:
            self.assertIn('#copy-account-number', script.read())


if __name__ == '__main__':
    unittest.main()
