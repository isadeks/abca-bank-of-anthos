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

"""Unit tests for the Back to home link on /savings-tips."""

from test_payment_deposit_handlers import HandlerTestCase


class TestSavingsTipsBackLink(HandlerTestCase):
    """The savings tips page links back to the home page"""

    def setUp(self):
        super().setUp()
        self.client.delete_cookie('token')

    def test_back_to_home_link(self):
        """Done means 1, Done means 2, Done means 3: public page has a
        Back to home link to /home below the tips list"""
        resp = self.client.get('/savings-tips')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('href="/home"', html)
        self.assertIn('Back to home', html)
        self.assertGreater(html.index('id="back-to-home"'),
                           html.index('</ul>'))
