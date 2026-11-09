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

"""Tests that the home page greets the signed-in user by first name."""

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


class TestHomeGreeting(unittest.TestCase):
    """The greeting uses the first word of the token's name"""

    def home(self, name):
        """Render the home page for a token carrying the given name"""
        token_data = {'user': 'testuser', 'acct': '1234567890', 'name': name}
        with patch('os.environ', dict(ENV)), \
                patch('frontend.open', mock_open(read_data='foo')), \
                patch('frontend.jwt.decode', return_value=token_data), \
                patch('frontend.ApiCall.make_call', return_value=None):
            client = frontend.create_app().test_client()
            client.set_cookie('token', 'abc')
            return client.get('/home')

    def test_greets_by_first_name(self):
        """Only the first name of a full name is used"""
        resp = self.home('Test User')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('id="greeting"', html)
        self.assertIn('data-first-name="Test"', html)
        self.assertIn('Hello, Test', html)
        self.assertNotIn('data-first-name="Test User"', html)

    def test_escapes_first_name(self):
        """The name is HTML-escaped"""
        html = self.home('<b>x</b> Y').get_data(as_text=True)
        self.assertNotIn('<b>x</b>', html)

    def test_no_greeting_without_name(self):
        """A token without a name shows no greeting"""
        html = self.home('').get_data(as_text=True)
        self.assertNotIn('id="greeting"', html)


if __name__ == '__main__':
    unittest.main()
