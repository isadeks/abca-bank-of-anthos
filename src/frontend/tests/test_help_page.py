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
The public Help page at /help.
"""

from test_payment_deposit_handlers import HandlerTestCase


class TestHelpPage(HandlerTestCase):
    """/help is public, has three FAQ entries and the shared chrome"""

    def test_help_page_without_sign_in(self):
        """no token cookie is needed"""
        self.client.delete_cookie('token')
        response = self.client.get('/help')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="help-title"', html)
        self.assertIn('How do I make a deposit?', html)
        self.assertIn('How do I send money?', html)
        self.assertIn('How do I sign out?', html)

    def test_help_page_has_header_and_footer(self):
        """the shared header and footer are rendered"""
        html = self.client.get('/help').get_data(as_text=True)
        self.assertIn('<header', html)
        self.assertIn('<footer', html)
