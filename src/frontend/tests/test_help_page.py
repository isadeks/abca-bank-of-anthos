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

"""Unit tests for the public /help page and the footer link."""

from test_payment_deposit_handlers import HandlerTestCase


class TestHelpPage(HandlerTestCase):
    """The help page needs no sign-in and is linked from the footer"""

    def setUp(self):
        super().setUp()
        self.client.delete_cookie('token')

    def test_help(self):
        """Done means 1 and 4: /help is public and shows contact details"""
        resp = self.client.get('/help')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        for text in ('1-800-555-0100', 'help@bank.example', '<footer'):
            self.assertIn(text, html)

    def test_footer_link(self):
        """Done means 2 and 4: footers link to /help like other links"""
        for path in ('/login', '/signup', '/help'):
            html = self.client.get(path).get_data(as_text=True)
            self.assertIn('<a href="/help" id="footer-help-link">Help</a>',
                          html)
