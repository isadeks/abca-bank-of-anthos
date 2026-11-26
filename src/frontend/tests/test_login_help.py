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

"""The sign-in page shows a plain-text help line under the Sign in button."""

import re

from test_payment_deposit_handlers import HandlerTestCase


class TestLoginHelp(HandlerTestCase):
    """Help line on the sign-in form"""

    def test_help_line_under_sign_in_button(self):
        """muted plain text, after the button, not a link"""
        self.client.delete_cookie('token')
        html = self.client.get('/login').get_data(as_text=True)
        text = 'Trouble signing in? Contact Cymbal Bank support.'
        self.assertIn(text, html)
        self.assertLess(html.index('>Sign in</button>'), html.index(text))
        match = re.search(r'<p id="login-help"[^>]*>(.*?)</p>', html)
        self.assertIsNotNone(match)
        self.assertIn('text-muted', match.group(0))
        self.assertNotIn('<a', match.group(1))
