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
The public /security-tips page.
"""

from test_payment_deposit_handlers import HandlerTestCase


class TestSecurityTips(HandlerTestCase):
    """/security-tips renders three tips without sign-in"""

    def get_page(self):
        """Request the page with no token cookie"""
        client = self.app.test_client()
        return client.get('/security-tips')

    def test_page_is_public(self):
        """no sign-in needed: 200, no redirect"""
        resp = self.get_page()
        self.assertEqual(resp.status_code, 200)

    def test_page_has_three_tips(self):
        """the title and the three tips are shown"""
        html = self.get_page().get_data(as_text=True)
        self.assertIn('Security tips', html)
        self.assertEqual(html.count('class="security-tip'), 3)
        self.assertIn('Never share your password', html)
        self.assertIn('Check the URL', html)
        self.assertIn('Sign out on shared computers', html)

    def test_page_has_shared_header_and_footer(self):
        """the shared navigation and footer are included"""
        html = self.get_page().get_data(as_text=True)
        self.assertIn('<footer', html)
        self.assertIn('<nav', html)
