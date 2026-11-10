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
The light / dark mode toggle is on every page and its assets are served.
"""

import os

from test_payment_deposit_handlers import HandlerTestCase


def static_file(path):
    """The text of a file under the frontend's static folder"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, 'static', path), encoding='utf-8') as f:
        return f.read()


class TestThemeToggle(HandlerTestCase):
    """The toggle button and the theme script are part of the page"""

    def test_login_page_has_toggle_and_script(self):
        """the signed out login page offers the toggle"""
        self.client.delete_cookie('token')
        resp = self.client.get('/login')
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="theme-toggle"', html)
        self.assertIn('static/scripts/theme.js', html)

    def test_signup_page_has_toggle(self):
        """the signup page offers the toggle"""
        self.client.delete_cookie('token')
        html = self.client.get('/signup').get_data(as_text=True)
        self.assertIn('id="theme-toggle"', html)

    def test_theme_script_stores_choice(self):
        """the script stores the choice and sets data-theme"""
        body = static_file('scripts/theme.js')
        self.assertIn('data-theme', body)
        self.assertIn('localStorage', body)

    def test_stylesheet_has_dark_rules(self):
        """the stylesheet restyles the page under data-theme=dark"""
        self.assertIn('html[data-theme="dark"] .card',
                      static_file('styles/cymbal.css'))
