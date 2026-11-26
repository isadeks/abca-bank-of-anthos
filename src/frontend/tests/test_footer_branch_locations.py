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
The footer link is named 'Branch locations'.
"""

from test_payment_deposit_handlers import HandlerTestCase, backend_response


class TestFooterBranchLocations(HandlerTestCase):
    """The footer link is named 'Branch locations'"""

    def test_footer_branch_locations(self):
        """the footer renders 'Branch locations' and keeps other links"""
        self.post.return_value = backend_response(400, 'nope')
        html = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='a' * 31).get_data(as_text=True)
        footer = html[html.index('<footer'):html.index('</footer>')]
        self.assertIn('<span>Branch locations</span>', footer)
        self.assertNotIn('<span>Locations</span>', footer)
        for link in ('Personal Banking', 'Business Banking', 'Loans'):
            self.assertIn('<span>%s</span>' % link, footer)
