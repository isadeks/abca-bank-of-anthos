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
Tests that the home page shows the account number masked to its last four
digits, with the full number only in the tooltip.
"""

import os
import re
import unittest
from unittest.mock import patch, mock_open

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
}
TOKEN_DATA = {'user': 'testuser', 'acct': '1234567890', 'name': 'Test'}


class TestAccountNumberMask(unittest.TestCase):
    """The home page masks the account number"""

    def setUp(self):
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.ApiCall.make_call', return_value=None),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'abc')

    def account_number_element(self):
        """The rendered account number element of the home page"""
        resp = self.client.get('/home')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        match = re.search(r'<span class="account-number"[^>]*>.*?</span>',
                          body, re.S)
        self.assertIsNotNone(match)
        return match.group(0)

    def test_shows_only_last_four_digits(self):
        """the visible text is masked and ends with the last 4 digits"""
        element = self.account_number_element()
        text = re.sub(r'<[^>]+>', '', element)
        self.assertIn('7890', text)
        self.assertNotIn('1234567890', text)
        self.assertNotIn('123456', text)

    def test_full_number_is_in_tooltip(self):
        """the full number stays available as the title attribute"""
        element = self.account_number_element()
        self.assertIn('title="1234567890"', element)


if __name__ == '__main__':
    unittest.main()
