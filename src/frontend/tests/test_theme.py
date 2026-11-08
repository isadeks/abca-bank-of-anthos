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
Tests for the frontend's dark mode (theme remembered in a cookie)
"""

import os
import unittest
from unittest.mock import patch, mock_open

from requests.exceptions import RequestException

import frontend

BASE_ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'ENABLE_TRACING': 'false',
    'METADATA_SERVER': 'metadata.invalid',
}


class TestThemeFromCookie(unittest.TestCase):
    """Tests how the cookie value maps to a theme"""

    def test_dark_cookie_is_dark(self):
        """the 'dark' value selects the dark theme"""
        self.assertEqual(frontend.theme_from_cookie('dark'), 'dark')

    def test_missing_or_unknown_cookie_is_light(self):
        """anything else, including no cookie, is the light theme"""
        for value in (None, '', 'light', 'DARK', 'solarized', '<script>'):
            self.assertEqual(frontend.theme_from_cookie(value), 'light')


class TestThemeRendering(unittest.TestCase):
    """Tests the pages rendered for each theme"""

    def setUp(self):
        with patch('frontend.open', mock_open(read_data='foo')), \
                patch('os.environ', dict(BASE_ENV)), \
                patch('frontend.requests.get', side_effect=RequestException):
            app = frontend.create_app()
        app.testing = True
        self.client = app.test_client()

    def get_login(self, theme=None):
        """Fetch the login page, optionally with a theme cookie"""
        if theme is not None:
            self.client.set_cookie('theme', theme, domain='localhost')
        return self.client.get('/login').get_data(as_text=True)

    def test_default_is_light(self):
        """without a cookie the page is light"""
        self.assertIn('data-theme="light"', self.get_login())

    def test_dark_cookie_renders_dark(self):
        """the dark cookie makes the server render the dark theme"""
        body = self.get_login('dark')
        self.assertIn('data-theme="dark"', body)
        self.assertIn('aria-pressed="true"', body)

    def test_unknown_cookie_renders_light(self):
        """an unrecognised cookie value cannot inject markup"""
        body = self.get_login('"><script>')
        self.assertIn('data-theme="light"', body)
        self.assertNotIn('<script>"', body)

    def test_toggle_is_in_the_header(self):
        """the toggle button is inside the header and its script is loaded"""
        body = self.get_login()
        header = body[body.index('<header>'):body.index('</header>')]
        self.assertIn('id="theme-toggle"', header)
        self.assertIn('static/scripts/theme.js', body)


if __name__ == '__main__':
    unittest.main()
