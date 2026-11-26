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

"""Unit tests for the public /fees and /hours pages and the footer links."""

from test_payment_deposit_handlers import HandlerTestCase


class TestInfoPages(HandlerTestCase):
    """The info pages need no sign-in and are linked from the footer"""

    def setUp(self):
        super().setUp()
        self.client.delete_cookie('token')

    def test_fees(self):
        """Done means 1 and 4: /fees is public and lists the fees"""
        resp = self.client.get('/fees')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        for text in ('Monthly account fee', 'Outgoing transfer',
                     'Paper statement', '$2 per month', '<table', '<footer'):
            self.assertIn(text, html)

    def test_hours(self):
        """Done means 2 and 4: /hours is public and lists the hours"""
        resp = self.client.get('/hours')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        for text in ('Mon–Fri', '9:00–17:00', 'Sat', '9:00–12:00',
                     'Sun', 'Closed', '<footer'):
            self.assertIn(text, html)

    def test_footer_links(self):
        """Done means 3: login and signup footers link to both pages"""
        for path in ('/login', '/signup'):
            html = self.client.get(path).get_data(as_text=True)
            self.assertIn('href="/fees"', html)
            self.assertIn('href="/hours"', html)
