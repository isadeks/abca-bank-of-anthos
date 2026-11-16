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
A sign-up the user service rejects with a 400 shows its message on the page.
"""

from requests.exceptions import ConnectionError as BackendDown

from test_payment_deposit_handlers import HandlerTestCase, backend_response

FORM = {'username': 'newuser', 'password': 'pw', 'firstname': ''}


class TestSignupError(HandlerTestCase):
    """The /signup POST handler"""

    def test_400_message_is_shown_above_form(self):
        """the userservice message is in an alert, no redirect"""
        self.post.return_value = backend_response(
            400, 'Please fill in every field.')
        resp = self.client.post('/signup', data=FORM)
        self.assertEqual(resp.status_code, 400)
        html = resp.get_data(as_text=True)
        self.assertIn('id="signup-error"', html)
        self.assertIn('Please fill in every field.', html)
        self.assertLess(html.index('id="signup-error"'),
                        html.index('id="signup-form"') + 2000)
        self.assertLess(html.index('id="signup-form"'),
                        html.index('id="signup-error"'))

    def test_message_is_escaped(self):
        """markup in the message is not rendered"""
        self.post.return_value = backend_response(400, '<b>x</b>')
        html = self.client.post('/signup', data=FORM).get_data(as_text=True)
        self.assertNotIn('<b>x</b>', html)

    def test_5xx_keeps_generic_redirect(self):
        """a server error redirects to login with the generic text"""
        self.post.return_value = backend_response(500, 'boom')
        resp = self.client.post('/signup', data=FORM)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('Account+creation+failed', resp.headers['Location'])

    def test_connection_error_keeps_generic_redirect(self):
        """an unreachable userservice redirects to login"""
        self.post.side_effect = BackendDown
        resp = self.client.post('/signup', data=FORM)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('Account+creation+failed', resp.headers['Location'])
