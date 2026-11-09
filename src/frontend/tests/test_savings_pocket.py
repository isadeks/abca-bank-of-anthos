"""
Tests for the Savings pocket on the frontend: the pocket card on the home
page and the route that moves the pocket's money back to the main account
"""

import html
import json
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open
from urllib.parse import parse_qs, urlparse

from requests.exceptions import HTTPError, RequestException

import frontend

ACCOUNT = '1234567890'
LOCAL = '883745000'
SAVINGS = '883745999'
TOKEN = {'acct': ACCOUNT, 'user': 'testuser', 'name': 'Test User'}

BASE_ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'TRANSACTIONS_API_ADDR': 'ledgerwriter:8080',
    'BALANCES_API_ADDR': 'balancereader:8080',
    'HISTORY_API_ADDR': 'transactionhistory:8080',
    'CONTACTS_API_ADDR': 'contacts:8080',
    'USERSERVICE_API_ADDR': 'userservice:8080',
    'LOCAL_ROUTING_NUM': LOCAL,
}


def response(body, status=200):
    """A fake requests response with a JSON body"""
    resp = MagicMock()
    resp.status_code = status
    resp.text = json.dumps(body)
    resp.json.return_value = body
    if status >= 400:
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


def make_app(savings=SAVINGS):
    """Create the app, with or without Savings pockets configured"""
    env = dict(BASE_ENV)
    if savings:
        env['SAVINGS_ROUTING_NUM'] = savings
    with patch('frontend.open', mock_open(read_data='foo')), \
            patch.dict(os.environ, env, clear=True), \
            patch('frontend.requests.get', side_effect=RequestException):
        app = frontend.create_app()
    app.config['TESTING'] = True
    return app


class FakeBackends:
    """Answers the frontend's GET calls from a dict of url fragments"""

    def __init__(self, pocket=0):
        self.pocket = pocket
        self.urls = []

    def get(self, url, **_kwargs):
        """Fake requests.get as used by ApiCall"""
        self.urls.append(url)
        if 'routing=' in url:
            return response(self.pocket)
        if '/balances/' in url:
            return response(10000)
        if '/transactions/' in url:
            return response([])
        return response([])


class PocketTestCase(unittest.TestCase):
    """Common setup: signed in client and patched backends"""

    savings = SAVINGS

    def setUp(self):
        self.app = make_app(self.savings)
        self.client = self.app.test_client()
        self.client.set_cookie('token', 'jwt')
        patches = [
            patch('frontend.jwt.decode', return_value=TOKEN),
            patch('frontend.sleep'),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.backends = FakeBackends()
        patcher = patch('api_call.get', side_effect=self.backends.get)
        patcher.start()
        self.addCleanup(patcher.stop)

    def message_after_redirect(self, resp):
        """The msg query parameter of the redirect to /home"""
        self.assertIn(resp.status_code, (302, 303))
        location = urlparse(resp.headers['Location'])
        self.assertEqual(location.path, '/home')
        return parse_qs(location.query)['msg'][0]

    def error_page(self, resp, status):
        """The home page rendered with an error message and a failure status"""
        self.assertEqual(resp.status_code, status)
        page = resp.get_data(as_text=True)
        self.assertIn('alert-message-error', page)
        return html.unescape(page)


class TestHomePocketCard(PocketTestCase):
    """The pocket card on the home page"""

    def test_pocket_balance_is_read_under_the_savings_routing_number(self):
        """the pocket balance comes from balancereader with ?routing=<savings>"""
        self.backends.pocket = 2550
        resp = self.client.get('/home')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(f'http://balancereader:8080/balances/{ACCOUNT}?routing={SAVINGS}',
                      self.backends.urls)
        page = resp.get_data(as_text=True)
        self.assertIn('id="pocket-card"', page)
        self.assertIn('$25.50', page)
        self.assertIn('Move to main account', page)

    def test_move_button_is_enabled_when_pocket_has_money(self):
        """the action is available for a funded pocket"""
        self.backends.pocket = 100
        page = self.client.get('/home').get_data(as_text=True)
        button = page.split('id="pocket-move-button"')[1].split('>')[0]
        self.assertNotIn('disabled', button)

    def test_move_button_is_disabled_when_pocket_is_empty(self):
        """the action is disabled for an empty pocket"""
        self.backends.pocket = 0
        page = self.client.get('/home').get_data(as_text=True)
        button = page.split('id="pocket-move-button"')[1].split('>')[0]
        self.assertIn('disabled', button)
        self.assertIn('$0.00', page.split('id="pocket-balance"')[1][:80])

    def test_no_pocket_card_when_savings_routing_is_not_configured(self):
        """without SAVINGS_ROUTING_NUM, home is as before"""
        self.app = make_app(savings=None)
        self.client = self.app.test_client()
        self.client.set_cookie('token', 'jwt')
        page = self.client.get('/home').get_data(as_text=True)
        self.assertNotIn('pocket-card', page)
        self.assertFalse(any('routing=' in u for u in self.backends.urls))


class TestMoveBack(PocketTestCase):
    """POST /pocket/move-back"""

    def test_moves_the_whole_pocket_to_the_main_account(self):
        """a transfer from savings to local, same account number, full balance"""
        self.backends.pocket = 4200
        with patch('frontend.requests.post', return_value=response('ok', 201)) as post:
            resp = self.client.post('/pocket/move-back', data={'uuid': 'u-1'})
        sent = json.loads(post.call_args.kwargs['data'])
        self.assertEqual(sent, {'fromAccountNum': ACCOUNT, 'fromRoutingNum': SAVINGS,
                                'toAccountNum': ACCOUNT, 'toRoutingNum': LOCAL,
                                'amount': 4200, 'uuid': 'u-1'})
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer jwt')
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(self.message_after_redirect(resp),
                         'Moved $42.00 from Savings to your main account')

    def test_empty_pocket_is_not_transferred(self):
        """nothing is submitted for an empty pocket"""
        self.backends.pocket = 0
        with patch('frontend.requests.post') as post:
            resp = self.client.post('/pocket/move-back', data={'uuid': 'u-1'})
        post.assert_not_called()
        self.assertIn('Move to main account failed: your Savings pocket is empty',
                      self.error_page(resp, 400))

    def test_unreadable_balance_is_reported(self):
        """an error from balancereader is shown, nothing is submitted"""
        with patch('api_call.get', side_effect=RequestException), \
                patch('frontend.requests.post') as post:
            resp = self.client.post('/pocket/move-back', data={'uuid': 'u-1'})
        post.assert_not_called()
        self.assertIn('could not read the Savings pocket balance',
                      self.error_page(resp, 502))

    def test_ledgerwriter_rejection_is_shown(self):
        """the ledgerwriter's reason is part of the error message"""
        self.backends.pocket = 100
        with patch('frontend.requests.post',
                   return_value=response('insufficient balance', 400)):
            resp = self.client.post('/pocket/move-back', data={'uuid': 'u-1'})
        self.assertIn('Move to main account failed: "insufficient balance"',
                      self.error_page(resp, 400))

    def test_ledgerwriter_unreachable_is_reported(self):
        """a network error gives a generic failure message"""
        self.backends.pocket = 100
        with patch('frontend.requests.post', side_effect=RequestException):
            resp = self.client.post('/pocket/move-back', data={'uuid': 'u-1'})
        self.assertIn('Move to main account failed',
                      self.error_page(resp, 502))

    def test_requires_login(self):
        """an invalid token gets 401 and nothing is read or submitted"""
        with patch('frontend.jwt.decode', side_effect=frontend.jwt.exceptions.InvalidTokenError), \
                patch('frontend.requests.post') as post:
            resp = self.client.post('/pocket/move-back', data={'uuid': 'u-1'})
        self.assertEqual(resp.status_code, 401)
        post.assert_not_called()

    def test_only_reads_the_signed_in_users_pocket(self):
        """the account comes from the token, not from the request"""
        self.backends.pocket = 100
        with patch('frontend.requests.post', return_value=response('ok', 201)) as post:
            self.client.post('/pocket/move-back',
                             data={'uuid': 'u-1', 'account': '9999999999'})
        sent = json.loads(post.call_args.kwargs['data'])
        self.assertEqual(sent['fromAccountNum'], ACCOUNT)
        self.assertEqual(sent['toAccountNum'], ACCOUNT)

    def test_unavailable_when_savings_routing_is_not_configured(self):
        """without SAVINGS_ROUTING_NUM the route submits nothing"""
        self.app = make_app(savings=None)
        self.client = self.app.test_client()
        self.client.set_cookie('token', 'jwt')
        with patch('frontend.requests.post') as post:
            resp = self.client.post('/pocket/move-back', data={'uuid': 'u-1'})
        post.assert_not_called()
        self.assertIn('not available', self.error_page(resp, 400))


if __name__ == '__main__':
    unittest.main()
