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
Tests of what the React single-page app is served and of the JSON API
that it talks to.
"""

import json
import unittest
from unittest.mock import MagicMock, patch, mock_open

import requests
from requests.exceptions import RequestException

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
    'DEFAULT_USERNAME': 'testuser',
    'DEFAULT_PASSWORD': 'bankofanthos',
    'REGISTERED_OAUTH_CLIENT_ID': 'client',
    'ALLOWED_OAUTH_REDIRECT_URI': 'https://client.example/callback',
}
TOKEN_DATA = {'user': 'testuser', 'acct': '1234567890', 'name': 'Test',
              'iat': 100, 'exp': 700}


def backend_response(status_code, payload=None, text=''):
    """A fake response of a backend service"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = payload
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(text)
    return resp


class ApiTestCase(unittest.TestCase):
    """A frontend whose backend services are mocked"""

    def setUp(self):
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.sleep'),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.get_patch = patch('frontend.requests.get', side_effect=RequestException)
        self.get = self.get_patch.start()
        self.addCleanup(self.get_patch.stop)
        self.post_patch = patch('frontend.requests.post')
        self.post = self.post_patch.start()
        self.addCleanup(self.post_patch.stop)
        self.client = frontend.create_app().test_client()

    def sign_in(self):
        """Give the client a token"""
        self.client.set_cookie('token', 'abc')


class TestShell(ApiTestCase):
    """The pages are the single-page app"""

    def test_login_page_is_the_app(self):
        """the login page is the app's HTML with a root element"""
        resp = self.client.get('/login')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="root"', resp.get_data(as_text=True))
        self.assertEqual(resp.headers['Cache-Control'], 'no-cache')

    def test_signup_page_is_the_app(self):
        """the signup page is the app's HTML"""
        resp = self.client.get('/signup')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="root"', resp.get_data(as_text=True))

    def test_home_needs_a_token(self):
        """a visitor without a token is sent to the login page"""
        resp = self.client.get('/home')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    def test_home_is_the_app_with_a_token(self):
        """the home page is the app's HTML for a signed in user"""
        self.sign_in()
        resp = self.client.get('/home')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="root"', resp.get_data(as_text=True))

    def test_flash_is_put_in_the_page(self):
        """the message of a failed payment is in the page for the app and the reader"""
        self.sign_in()
        resp = self.client.post('/payment', data={
            'account_num': '9999999999', 'amount': 'abc', 'uuid': 'u'})
        body = resp.get_data(as_text=True)
        flash = body.split('<script id="boa-flash" type="application/json">')[1]
        flash = json.loads(flash.split('</script>')[0])
        self.assertTrue(flash['isError'])
        self.assertIn('abc is not a valid number', flash['message'])
        self.assertNotIn(frontend.FLASH_MARKER, body)

    def test_flash_is_escaped(self):
        """a message cannot inject markup or close the script element"""
        markup = frontend.flash_markup({'message': '</script><b>x</b>', 'isError': True})
        self.assertNotIn('<b>x</b>', markup)
        self.assertEqual(markup.count('</script>'), 1)

    def test_no_flash_leaves_no_marker(self):
        """the marker is removed when there is no message"""
        self.assertNotIn(frontend.FLASH_MARKER, frontend.render_shell())


class TestSessionApi(ApiTestCase):
    """/api/config and /api/session"""

    def test_config(self):
        """the app learns the deployment and the demo credentials"""
        resp = self.client.get('/api/config')
        self.assertEqual(resp.status_code, 200)
        config = resp.get_json()
        self.assertEqual(config['default_username'], 'testuser')
        self.assertEqual(config['default_password'], 'bankofanthos')
        self.assertEqual(config['bank_name'], 'Bank of Anthos')
        self.assertFalse(config['cymbal_logo'])

    def test_session_needs_a_token(self):
        """without a token the session is 401"""
        self.assertEqual(self.client.get('/api/session').status_code, 401)

    def test_session(self):
        """with a token the session names the user"""
        self.sign_in()
        resp = self.client.get('/api/session')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {
            'name': 'Test', 'username': 'testuser', 'account_id': '1234567890'})

    def test_logout_deletes_the_cookies(self):
        """logging out deletes the token and points the app at the login"""
        self.sign_in()
        resp = self.client.post('/api/logout')
        self.assertEqual(resp.get_json(), {'redirect': '/login'})
        cookies = ' '.join(resp.headers.getlist('Set-Cookie'))
        self.assertIn('token=;', cookies)


class TestLoginApi(ApiTestCase):
    """/api/login and /api/signup"""

    def test_login(self):
        """valid credentials set the cookie and go home"""
        self.get.side_effect = None
        self.get.return_value = backend_response(200, {'token': 'tok'})
        resp = self.client.post('/api/login', json={'username': 'a', 'password': 'b'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {'redirect': '/home'})
        self.assertIn('token=tok', resp.headers['Set-Cookie'])
        self.assertIn('Max-Age=600', resp.headers['Set-Cookie'])

    def test_login_in_an_oauth_flow_goes_to_consent(self):
        """a login that is part of an oauth flow goes on to the consent form"""
        self.get.side_effect = None
        self.get.return_value = backend_response(200, {'token': 'tok'})
        resp = self.client.post('/api/login', json={
            'username': 'a', 'password': 'b', 'response_type': 'code',
            'state': 's', 'redirect_uri': 'https://client.example/callback',
            'app_name': 'App'})
        location = resp.get_json()['redirect']
        self.assertTrue(location.startswith('/consent?'))
        self.assertIn('state=s', location)
        self.assertIn('app_name=App', location)

    def test_login_failure(self):
        """credentials userservice refuses give 401 and no cookie"""
        self.get.side_effect = None
        self.get.return_value = backend_response(401, text='bad')
        resp = self.client.post('/api/login', json={'username': 'a', 'password': 'b'})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json(), {'error': 'Login failed'})
        self.assertNotIn('Set-Cookie', resp.headers)

    def test_login_unreachable_userservice(self):
        """a userservice that cannot be reached is a failed login"""
        resp = self.client.post('/api/login', json={'username': 'a', 'password': 'b'})
        self.assertEqual(resp.status_code, 401)

    def test_signup_logs_in(self):
        """a created account is logged in"""
        self.post.return_value = backend_response(201)
        self.get.side_effect = None
        self.get.return_value = backend_response(200, {'token': 'tok'})
        resp = self.client.post('/api/signup', json={
            'username': 'new', 'password': 'pw', 'password-repeat': 'pw'})
        self.assertEqual(resp.get_json(), {'redirect': '/home'})
        self.assertIn('token=tok', resp.headers['Set-Cookie'])
        self.assertEqual(self.post.call_args.kwargs['data']['username'], 'new')

    def test_signup_without_login_goes_to_login(self):
        """an account that cannot be logged in yet sends the user to the login"""
        self.post.return_value = backend_response(201)
        resp = self.client.post('/api/signup', json={'username': 'new', 'password': 'pw'})
        self.assertEqual(resp.get_json(), {'redirect': '/login'})

    def test_signup_failure(self):
        """userservice refusing the account gives 400"""
        self.post.return_value = backend_response(400, text='exists')
        resp = self.client.post('/api/signup', json={'username': 'new', 'password': 'pw'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {'error': 'Account creation failed'})


class TestHomeApi(ApiTestCase):
    """/api/home"""

    def test_home_needs_a_token(self):
        """without a token the home data is 401"""
        self.assertEqual(self.client.get('/api/home').status_code, 401)

    def test_home(self):
        """balance, history and contacts are gathered for the app"""
        history = [{'fromAccountNum': '1234567890', 'toAccountNum': '1111111111',
                    'amount': 500, 'timestamp': '2021-03-07T12:00:00.000+0000'}]
        contacts = [{'label': 'Alice', 'account_num': '1111111111',
                     'routing_num': '883745000', 'is_external': False}]
        answers = {'balances': 12345, 'history': history, 'contacts': contacts}

        def make_call(call):
            name = call.display_name
            return backend_response(200, answers[
                'balances' if 'balance' in name.lower() else
                'history' if 'transaction' in name.lower() else 'contacts'])

        self.sign_in()
        with patch('frontend.ApiCall.make_call', autospec=True, side_effect=make_call):
            resp = self.client.get('/api/home')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['account_id'], '1234567890')
        self.assertEqual(data['name'], 'Test')
        self.assertEqual(data['balance'], 12345)
        self.assertEqual(data['contacts'], contacts)
        self.assertEqual(data['history'][0]['accountLabel'], 'Alice')

    def test_home_with_unavailable_backends(self):
        """what cannot be loaded is null (or empty) rather than an error"""
        self.sign_in()
        with patch('frontend.ApiCall.make_call', return_value=None):
            data = self.client.get('/api/home').get_json()
        self.assertIsNone(data['balance'])
        self.assertIsNone(data['history'])
        self.assertEqual(data['contacts'], [])


class TestTransactionApi(ApiTestCase):
    """/api/payment and /api/deposit"""

    def test_transactions_need_a_token(self):
        """no token, no transaction"""
        self.assertEqual(self.client.post('/api/payment', json={}).status_code, 401)
        self.assertEqual(self.client.post('/api/deposit', json={}).status_code, 401)
        self.post.assert_not_called()

    def test_payment(self):
        """a payment is sent to the ledger in cents"""
        self.sign_in()
        self.post.return_value = backend_response(201)
        resp = self.client.post('/api/payment', json={
            'account_num': '9999999999', 'amount': '12.5', 'uuid': 'u1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {'message': 'Payment successful'})
        sent = json.loads(self.post.call_args.kwargs['data'])
        self.assertEqual(sent['amount'], 1250)
        self.assertEqual(sent['toAccountNum'], '9999999999')
        self.assertEqual(sent['fromAccountNum'], '1234567890')

    def test_payment_rejected(self):
        """a payment the ledger refuses reports the reason"""
        self.sign_in()
        self.post.return_value = backend_response(400, text='insufficient balance')
        resp = self.client.post('/api/payment', json={
            'account_num': '9999999999', 'amount': '12.5', 'uuid': 'u1'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Payment failed: insufficient balance', resp.get_json()['error'])

    def test_payment_invalid_amount(self):
        """an amount that is not a number is refused before the ledger is asked"""
        self.sign_in()
        resp = self.client.post('/api/payment', json={
            'account_num': '9999999999', 'amount': 'abc', 'uuid': 'u1'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('abc is not a valid number', resp.get_json()['error'])
        self.post.assert_not_called()

    def test_deposit_from_a_saved_account(self):
        """the saved account arrives as JSON text, as the select's value"""
        self.sign_in()
        self.post.return_value = backend_response(201)
        account = json.dumps({'account_num': '1111111111', 'routing_num': '123456789'})
        resp = self.client.post('/api/deposit', json={
            'account': account, 'amount': '20', 'uuid': 'u2'})
        self.assertEqual(resp.get_json(), {'message': 'Deposit successful'})
        sent = json.loads(self.post.call_args.kwargs['data'])
        self.assertEqual(sent['fromAccountNum'], '1111111111')
        self.assertEqual(sent['fromRoutingNum'], '123456789')
        self.assertEqual(sent['toAccountNum'], '1234567890')
        self.assertEqual(sent['amount'], 2000)

    def test_deposit_from_the_local_routing_number_is_refused(self):
        """a new external account cannot use the bank's own routing number"""
        self.sign_in()
        resp = self.client.post('/api/deposit', json={
            'account': 'add', 'external_account_num': '1111111111',
            'external_routing_num': '883745000', 'amount': '20', 'uuid': 'u2'})
        self.assertEqual(resp.status_code, 400)
        self.post.assert_not_called()


class TestConsentApi(ApiTestCase):
    """/api/consent"""

    def test_consent_needs_a_token(self):
        """no token, no consent"""
        resp = self.client.post('/api/consent', json={'consent': True})
        self.assertEqual(resp.status_code, 401)

    def test_consent_to_an_unknown_client_is_refused(self):
        """only the registered client's redirect uri is followed"""
        self.sign_in()
        resp = self.client.post('/api/consent', json={
            'consent': True, 'state': 's', 'redirect_uri': 'https://evil.example/'})
        self.assertEqual(resp.status_code, 400)
        self.post.assert_not_called()

    def test_deny(self):
        """a denial goes back to the client with an error"""
        self.sign_in()
        resp = self.client.post('/api/consent', json={
            'consent': False, 'state': 's',
            'redirect_uri': 'https://client.example/callback'})
        self.assertEqual(resp.get_json(), {
            'redirect': 'https://client.example/callback#error=access_denied'})

    def test_approve(self):
        """an approval goes where the client sends the browser, and is remembered"""
        self.sign_in()
        callback = MagicMock()
        callback.status_code = requests.codes.found
        callback.headers = {'Location': 'https://client.example/done'}
        self.post.return_value = callback
        resp = self.client.post('/api/consent', json={
            'consent': True, 'state': 's',
            'redirect_uri': 'https://client.example/callback'})
        self.assertEqual(resp.get_json(), {'redirect': 'https://client.example/done'})
        self.assertIn('consented=true', resp.headers['Set-Cookie'])


if __name__ == '__main__':
    unittest.main()
