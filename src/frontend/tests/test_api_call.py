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

"""Unit tests for ApiCall.make_call with requests.get mocked."""

import os
import sys
import unittest
from unittest import mock

from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import RequestException, Timeout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api_call import ApiCall, ApiRequest  # noqa: E402


class TestApiCall(unittest.TestCase):
    """make_call returns the response or logs and returns None"""

    def setUp(self):
        self.request = ApiRequest('http://svc/path', {'Authorization': 'x'}, 3)
        self.logger = mock.Mock()
        self.call = ApiCall('balance', self.request, self.logger)

    @mock.patch('api_call.get')
    def test_success(self, mock_get):
        """Done means 1, Done means 2: response returned, args passed"""
        resp = mock.Mock()
        mock_get.return_value = resp
        self.assertIs(self.call.make_call(), resp)
        mock_get.assert_called_once_with(
            url='http://svc/path', headers={'Authorization': 'x'}, timeout=3)
        self.logger.error.assert_not_called()

    def test_request_exceptions(self):
        """Done means 3: RequestException is logged once, returns None"""
        for exc in (ReqConnectionError('refused'), Timeout('slow'),
                    RequestException('boom')):
            with self.subTest(exc=type(exc).__name__):
                self.logger.reset_mock()
                with mock.patch('api_call.get', side_effect=exc):
                    self.assertIsNone(self.call.make_call())
                self.logger.error.assert_called_once_with(
                    'Error getting %s: %s', 'balance', str(exc))

    @mock.patch('api_call.get', side_effect=ValueError('bad url'))
    def test_value_error(self, _mock_get):
        """Done means 4: ValueError is logged, returns None"""
        self.assertIsNone(self.call.make_call())
        self.logger.error.assert_called_once_with(
            'Error getting %s: %s', 'balance', 'bad url')


if __name__ == '__main__':
    unittest.main()
