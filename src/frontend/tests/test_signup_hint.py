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
The sign-up page hints at the allowed username characters.
"""

from test_payment_deposit_handlers import HandlerTestCase


class TestSignupHint(HandlerTestCase):
    """The username box on the sign-up page has a hint"""

    def test_signup_page_has_username_hint(self):
        """the rendered sign-up page shows the hint under the username input"""
        self.client.delete_cookie('token')
        html = self.client.get('/signup').get_data(as_text=True)
        self.assertIn('id="signup-username-hint"', html)
        self.assertIn('Letters and numbers only.', html)
        self.assertLess(html.index('id="signup-username"'),
                        html.index('id="signup-username-hint"'))
