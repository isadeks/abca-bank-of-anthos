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
Tests that every page has a footer linking to Help, Privacy and Contact,
and that those links lead to pages.
"""

import unittest
from unittest.mock import patch, mock_open

from requests.exceptions import RequestException

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
}


class TestFooterLinks(unittest.TestCase):
    """The footer links to the support pages"""

    def setUp(self):
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.requests.get', side_effect=RequestException),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.client = frontend.create_app().test_client()

    def test_login_page_has_footer_links(self):
        """pages that include the footer show the three links"""
        body = self.client.get('/login').get_data(as_text=True)
        self.assertIn('href="/help">Help</a>', body)
        self.assertIn('href="/privacy">Privacy</a>', body)
        self.assertIn('href="/contact">Contact</a>', body)

    def test_support_pages_render_with_footer(self):
        """each link target answers 200 with its title and the footer"""
        for path, title in (('/help', 'Help'), ('/privacy', 'Privacy'),
                            ('/contact', 'Contact')):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200)
            body = resp.get_data(as_text=True)
            self.assertIn(f'id="support-title" class="mb-4 header-title">{title}<', body)
            self.assertIn('id="footer-links"', body)
