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

"""The public landing page at / and the signed-in redirect to the home page."""

from unittest.mock import patch

import jwt

from test_payment_deposit_handlers import HandlerTestCase


class TestLandingPage(HandlerTestCase):
    """/ shows a landing page before sign-in"""

    def test_anonymous_sees_landing_page(self):
        """no valid token: hero, sign-in link and the info sections"""
        with patch('frontend.jwt.decode', side_effect=jwt.InvalidTokenError):
            resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('id="landing-hero"', html)
        self.assertIn('href="/login"', html)
        for section in ('personal', 'business', 'rates', 'contact'):
            self.assertIn('id="landing-%s"' % section, html)

    def test_signed_in_gets_home_page(self):
        """a valid token still goes to the account home page"""
        resp = self.client.get('/')
        self.assertNotIn('id="landing-hero"', resp.get_data(as_text=True))
