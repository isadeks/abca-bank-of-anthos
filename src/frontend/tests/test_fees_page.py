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
The static /fees page and its footer link.
"""

from test_payment_deposit_handlers import HandlerTestCase


class TestFeesPage(HandlerTestCase):
    """/fees is public, static and linked from the footer"""

    def test_fees_page_content(self):
        """the page states transfers and deposits are free"""
        self.client.delete_cookie('token')
        resp = self.client.get('/fees')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('Transfers between customers are free of charge', html)
        self.assertIn('Deposits are free', html)

    def test_footer_links_to_fees(self):
        """the footer of the fees page links to /fees"""
        html = self.client.get('/fees').get_data(as_text=True)
        self.assertIn('<footer', html)
        self.assertIn('href="/fees"', html)
