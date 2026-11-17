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
The page footer shows the balance service version.
"""

from unittest.mock import patch

from requests.exceptions import ConnectTimeout

from test_payment_deposit_handlers import HandlerTestCase, backend_response


class TestFooterBalanceVersion(HandlerTestCase):
    """The footer calls the balance service /version endpoint"""

    def render(self):
        """render a page that includes the footer"""
        self.post.return_value = backend_response(400, 'nope')
        return self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='a' * 31).get_data(as_text=True)

    def test_version_shown(self):
        """a successful call shows the version with a short timeout"""
        with patch('frontend.requests.get',
                   return_value=backend_response(200, '1.2.3\n')) as get:
            html = self.render()
        self.assertIn('Balance service: </b>1.2.3', html)
        self.assertTrue(get.call_args.args[0].endswith('/version'))
        self.assertLessEqual(get.call_args.kwargs['timeout'], 2)

    def test_failure_shows_nothing(self):
        """a timeout hides the item and the page still loads"""
        with patch('frontend.requests.get', side_effect=ConnectTimeout):
            html = self.render()
        self.assertIn('<footer', html)
        self.assertNotIn('Balance service', html)

    def test_error_status_shows_nothing(self):
        """an HTTP error hides the item"""
        with patch('frontend.requests.get',
                   return_value=backend_response(500, 'boom')):
            html = self.render()
        self.assertNotIn('Balance service', html)
