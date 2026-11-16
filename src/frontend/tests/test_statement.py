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
Unit tests for the monthly statement download.
"""

from unittest.mock import patch

from requests.exceptions import RequestException

from test_payment_deposit_handlers import (
    HandlerTestCase, backend_response, ACCOUNT_ID)


class TestStatement(HandlerTestCase):
    """/statement proxies the history service's CSV"""

    def test_home_has_download_form(self):
        """the home page offers a month picker and download button"""
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('id="statement-month"', html)
        self.assertIn('type="month"', html)
        self.assertIn('Download statement', html)

    def test_downloads_csv(self):
        """the CSV is returned as an attachment"""
        with patch('frontend.requests.get',
                   return_value=backend_response(200, 'a,b\n')) as get:
            resp = self.client.get('/statement?month=2024-03')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_data(as_text=True), 'a,b\n')
        self.assertIn('text/csv', resp.headers['Content-Type'])
        self.assertIn('statement-2024-03.csv',
                      resp.headers['Content-Disposition'])
        self.assertEqual(get.call_args.kwargs['url'],
                         f'http://None/statements/{ACCOUNT_ID}')
        self.assertEqual(get.call_args.kwargs['params'],
                         {'month': '2024-03'})

    def test_bad_month(self):
        """an invalid month is rejected without calling the backend"""
        with patch('frontend.requests.get') as get:
            resp = self.client.get('/statement?month=March')
        self.assertEqual(resp.status_code, 400)
        get.assert_not_called()

    def test_backend_failure(self):
        """a backend error gives 502"""
        with patch('frontend.requests.get', side_effect=RequestException):
            resp = self.client.get('/statement?month=2024-03')
        self.assertEqual(resp.status_code, 502)

    def test_requires_login(self):
        """no token redirects to login"""
        self.client.delete_cookie('token')
        resp = self.client.get('/statement?month=2024-03')
        self.assertEqual(resp.status_code, 302)
