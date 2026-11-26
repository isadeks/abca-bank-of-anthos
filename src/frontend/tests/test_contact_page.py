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
The static /contact page and its footer link.
"""

from test_payment_deposit_handlers import HandlerTestCase


class TestContactPage(HandlerTestCase):
    """/contact is public, static and linked from the footer"""

    def test_contact_page_content(self):
        """the page shows the support email and opening hours"""
        self.client.delete_cookie('token')
        resp = self.client.get('/contact')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('support@larkspur-demo.example', html)
        self.assertIn('Opening hours', html)

    def test_footer_links_to_contact(self):
        """the footer links to /contact next to the Fees link"""
        html = self.client.get('/contact').get_data(as_text=True)
        self.assertIn('<footer', html)
        self.assertIn('href="/contact"', html)
        self.assertIn('href="/fees"', html)
