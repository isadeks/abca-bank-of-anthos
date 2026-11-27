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
The home page greets the signed-in user by first name.
"""

from unittest.mock import patch

from test_payment_deposit_handlers import HandlerTestCase, TOKEN_DATA


class TestHomeGreeting(HandlerTestCase):
    """Greeting on /home"""

    def home(self, name):
        """Render /home for a token carrying the given name"""
        data = dict(TOKEN_DATA, name=name)
        with patch('frontend.jwt.decode', return_value=data):
            return self.client.get('/home').get_data(as_text=True)

    def test_greets_by_first_name(self):
        """Done means 1: only the first word of the full name is used"""
        html = self.home('Bob Anthos Smith')
        self.assertIn('Welcome back, Bob<', html)
        self.assertNotIn('Anthos', html.split('Welcome back')[1][:20])

    def test_no_name_keeps_current_header(self):
        """Done means 2: no usable name, no greeting"""
        for name in ('', '   ', None):
            html = self.home(name)
            self.assertNotIn('Welcome back', html)
            self.assertIn('Checking Account', html)
