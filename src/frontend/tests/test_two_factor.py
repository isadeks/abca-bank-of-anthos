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
Frontend flows for optional two-factor sign-in: the second login step and the
security page (set up, confirm, recovery codes, turn off).
"""

from unittest.mock import patch

from test_payment_deposit_handlers import HandlerTestCase, TOKEN_DATA, backend_response

SECRET = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'
URI = 'otpauth://totp/Bank%20of%20Anthos%3Atestuser?secret=' + SECRET
SESSION = dict(TOKEN_DATA, iat=1000, exp=4600)


def json_response(status_code, body, text=''):
    """A fake userservice response with a JSON body"""
    resp = backend_response(status_code, text)
    resp.json.return_value = body
    return resp


class TwoFactorTestCase(HandlerTestCase):
    """Adds a mock for GET requests to the userservice"""

    def setUp(self):
        super().setUp()
        self.get = patch('frontend.requests.get').start()
        patch('frontend.jwt.decode', return_value=SESSION).start()

    def twofa_calls(self, path):
        """The mocked posts that went to a userservice 2FA endpoint"""
        url = self.app.config['TWOFA_URI'] + path
        return [c for c in self.post.call_args_list if c.args and c.args[0] == url]


class TestLogin(TwoFactorTestCase):
    """Signing in with and without a second factor"""

    def test_login_without_2fa_sets_the_cookie(self):
        """users without 2FA sign in as before"""
        self.client.delete_cookie('token')
        self.get.return_value = json_response(200, {'token': 'jwt'})
        resp = self.client.post('/login', data={'username': 'testuser', 'password': 'pw'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('token=jwt', resp.headers['Set-Cookie'])

    def test_password_step_asks_for_the_code(self):
        """a 2FA user gets the code form, and no cookie"""
        self.client.delete_cookie('token')
        self.get.return_value = json_response(
            401, {'mfa_required': True, 'mfa_token': 'mfa-1'})
        resp = self.client.post('/login', data={'username': 'testuser', 'password': 'pw'})
        page = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="login-code"', page)
        self.assertIn('value="mfa-1"', page)
        self.assertNotIn('login-password', page)
        self.assertNotIn('Set-Cookie', resp.headers)

    def test_code_step_sends_token_and_code_but_not_the_password(self):
        """the second request carries mfa_token and code"""
        self.client.delete_cookie('token')
        self.get.return_value = json_response(200, {'token': 'jwt'})
        resp = self.client.post('/login', data={
            'username': 'testuser', 'mfa_token': 'mfa-1', 'code': '123456'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('token=jwt', resp.headers['Set-Cookie'])
        params = self.get.call_args.kwargs['params']
        self.assertEqual(params, {'username': 'testuser', 'mfa_token': 'mfa-1',
                                  'code': '123456'})

    def test_wrong_code_shows_the_form_again(self):
        """a rejected code keeps the user on the code form"""
        self.client.delete_cookie('token')
        self.get.return_value = backend_response(401, 'invalid code')
        resp = self.client.post('/login', data={
            'username': 'testuser', 'mfa_token': 'mfa-1', 'code': '000000'})
        page = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 401)
        self.assertIn('That code was not accepted.', page)
        self.assertIn('value="mfa-1"', page)
        self.assertNotIn('Set-Cookie', resp.headers)

    def test_rate_limited_code_is_reported(self):
        """a 429 from the userservice is explained"""
        self.client.delete_cookie('token')
        self.get.return_value = backend_response(429, 'too many attempts')
        resp = self.client.post('/login', data={
            'username': 'testuser', 'mfa_token': 'mfa-1', 'code': '000000'})
        self.assertIn('Too many attempts', resp.get_data(as_text=True))

    def test_expired_mfa_token_goes_back_to_login(self):
        """a refused mfa_token restarts the sign-in"""
        self.client.delete_cookie('token')
        self.get.return_value = backend_response(401, 'invalid login')
        resp = self.client.post('/login', data={
            'username': 'testuser', 'mfa_token': 'old', 'code': '123456'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('Login+Failed', resp.headers['Location'])


class TestSecurityPage(TwoFactorTestCase):
    """Turning two-factor sign-in on and off"""

    def status(self, enabled, left=0):
        """Make the userservice report the 2FA state"""
        self.get.return_value = json_response(
            200, {'enabled': enabled, 'recovery_codes_left': left})

    def test_page_needs_a_session(self):
        """without a token the user is sent to login"""
        self.client.delete_cookie('token')
        resp = self.client.get('/security')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    def test_page_offers_setup_when_off(self):
        """the off state has a Set up button"""
        self.status(False)
        page = self.client.get('/security').get_data(as_text=True)
        self.assertIn('id="setup-submit"', page)
        self.assertNotIn('id="disable-form"', page)

    def test_page_offers_turning_off_when_on(self):
        """the on state shows the recovery codes left and a disable form"""
        self.status(True, 5)
        page = self.client.get('/security').get_data(as_text=True)
        self.assertIn('id="disable-form"', page)
        self.assertIn('5 recovery codes left', page)

    def test_setup_shows_qr_code_and_secret(self):
        """setup renders an inline QR code, the secret and the confirm form"""
        self.status(False)
        self.post.return_value = json_response(200, {'secret': SECRET, 'uri': URI})
        page = self.client.post('/security/setup').get_data(as_text=True)
        self.assertIn('<svg', page)
        self.assertIn(SECRET, page)
        self.assertIn('id="enable-form"', page)
        headers = self.twofa_calls('/setup')[0].kwargs['headers']
        self.assertEqual(headers, {'Authorization': 'Bearer abc'})

    def test_enable_shows_recovery_codes(self):
        """a confirmed code shows the 8 recovery codes"""
        self.status(True, 8)
        codes = ['AAAAA-BBBB%d' % i for i in range(8)]
        self.post.return_value = json_response(200, {'recovery_codes': codes})
        resp = self.client.post('/security/enable', data={'code': '123456'})
        page = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        for code in codes:
            self.assertIn(code, page)
        self.assertIn('will not be shown again', page)
        self.assertEqual(self.twofa_calls('/enable')[0].kwargs['data'], {'code': '123456'})

    def test_enable_with_wrong_code_keeps_the_setup(self):
        """a rejected code shows the same QR code again"""
        self.status(False)
        self.post.return_value = backend_response(401, 'invalid code')
        resp = self.client.post('/security/enable',
                                data={'code': '000000', 'secret': SECRET, 'uri': URI})
        page = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 401)
        self.assertIn('That code was not accepted.', page)
        self.assertIn(SECRET, page)
        self.assertNotIn('recovery-codes', page)

    def test_enable_ignores_a_tampered_secret(self):
        """hidden fields are validated before they are shown again"""
        self.status(False)
        self.post.return_value = backend_response(401, 'invalid code')
        resp = self.client.post('/security/enable', data={
            'code': '000000', 'secret': '<script>', 'uri': 'javascript:1'})
        self.assertNotIn('<script>', resp.get_data(as_text=True))

    def test_disable_with_code(self):
        """a confirmed code turns 2FA off"""
        self.status(False)
        self.post.return_value = json_response(200, {})
        resp = self.client.post('/security/disable', data={'code': '123456'})
        self.assertIn('Two-factor sign-in is off.', resp.get_data(as_text=True))
        self.assertEqual(self.twofa_calls('/disable')[0].kwargs['data'], {'code': '123456'})

    def test_disable_with_wrong_code(self):
        """a rejected code leaves 2FA on and says so"""
        self.status(True, 8)
        self.post.return_value = backend_response(401, 'invalid code')
        resp = self.client.post('/security/disable', data={'code': '000000'})
        page = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 401)
        self.assertIn('That code was not accepted.', page)
        self.assertIn('id="disable-form"', page)

    def test_actions_need_a_session(self):
        """no token, no calls to the userservice"""
        self.client.delete_cookie('token')
        for path in ('/security/setup', '/security/enable', '/security/disable'):
            self.assertEqual(self.client.post(path).status_code, 302)
        self.post.assert_not_called()
