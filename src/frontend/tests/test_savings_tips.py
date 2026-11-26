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

"""Unit tests for the public /savings-tips page and its footer link."""

from test_payment_deposit_handlers import HandlerTestCase


class TestSavingsTips(HandlerTestCase):
    """The savings tips page needs no sign-in and is linked from the footer"""

    def setUp(self):
        super().setUp()
        self.client.delete_cookie('token')

    def test_savings_tips(self):
        """/savings-tips is public and lists five tips"""
        resp = self.client.get('/savings-tips')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('Savings tips', html)
        self.assertEqual(html.count('<li>'), 6)
        self.assertIn('<footer', html)

    def test_footer_link(self):
        """Footer links to the page"""
        for path in ('/login', '/signup'):
            html = self.client.get(path).get_data(as_text=True)
            self.assertIn('href="/savings-tips"', html)
