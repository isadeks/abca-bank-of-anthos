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
The page footer no longer shows the copyright line.
"""

from test_payment_deposit_handlers import HandlerTestCase, backend_response


class TestFooter(HandlerTestCase):
    """The footer keeps the demo disclaimer but not the copyright line"""

    def test_footer_has_no_copyright_line(self):
        """a rendered page has the disclaimer and no 2020-2024 line"""
        self.post.return_value = backend_response(400, 'nope')
        html = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='a' * 31).get_data(as_text=True)
        self.assertIn('<footer', html)
        self.assertIn('This website is hosted for demo purposes only', html)
        self.assertNotIn('2020-2024', html)
        self.assertNotIn('footer-google-inc', html)
