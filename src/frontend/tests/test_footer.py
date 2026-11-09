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
Tests that the page footer shows the app version and the environment name.
"""

import unittest
from unittest.mock import patch, mock_open

from requests.exceptions import RequestException

import frontend

BASE_ENV = {
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
}
PAGES = ['/login', '/signup']


class TestFooter(unittest.TestCase):
    """Every page footer carries the version and environment"""

    def client(self, **env):
        """A test client for an app created with the given environment"""
        environ = dict(BASE_ENV)
        environ.update(env)
        patches = [
            patch('os.environ', environ),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.requests.get', side_effect=RequestException),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        return frontend.create_app().test_client()

    def test_footer_shows_version_and_namespace(self):
        """the version and the Kubernetes namespace are shown"""
        client = self.client(VERSION='v1.2.3', K8S_NAMESPACE_NAME='pr-42')
        for page in PAGES:
            body = client.get(page).get_data(as_text=True)
            self.assertIn('<span id="app-version">v1.2.3</span>', body)
            self.assertIn('<span id="app-environment">pr-42</span>', body)

    def test_environment_name_overrides_namespace(self):
        """ENVIRONMENT_NAME wins over the namespace"""
        client = self.client(VERSION='v1', K8S_NAMESPACE_NAME='boa',
                             ENVIRONMENT_NAME='staging')
        body = client.get('/login').get_data(as_text=True)
        self.assertIn('<span id="app-environment">staging</span>', body)

    def test_footer_defaults(self):
        """without configuration the footer says unknown and local"""
        client = self.client()
        body = client.get('/login').get_data(as_text=True)
        self.assertIn('<span id="app-version">unknown</span>', body)
        self.assertIn('<span id="app-environment">local</span>', body)
