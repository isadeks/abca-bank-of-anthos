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
Unit tests for the /payment and /deposit handlers: authentication, form
validation, the requests sent to ledgerwriter and contacts, backend errors
and redirects.
"""

import json
import unittest
from unittest.mock import MagicMock, patch, mock_open

import jwt
import requests
from requests.exceptions import RequestException

import frontend

LOCAL_ROUTING = '883745000'
ACCOUNT_ID = '1234567890'
ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': LOCAL_ROUTING,
}
TOKEN_DATA = {'user': 'testuser', 'acct': ACCOUNT_ID, 'name': 'Test'}
SAVED_ACCOUNT = json.dumps({'account_num': '5555555555',
                            'routing_num': '123456789'})


def backend_response(status_code, text=''):
    """A fake backend response"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(text)
    return resp


class HandlerTestCase(unittest.TestCase):
    """Builds the app with every backend call mocked"""

    def setUp(self):
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.requests.get', side_effect=RequestException),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.ApiCall.make_call', return_value=None),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.sleep = patch('frontend.sleep').start()
        self.post = patch('frontend.requests.post',
                          return_value=backend_response(201)).start()
        self.addCleanup(patch.stopall)
        self.app = frontend.create_app()
        self.client = self.app.test_client()
        self.client.set_cookie('token', 'abc')

    def payment(self, **overrides):
        """Submit a payment form to an existing account"""
        form = {'account_num': '9999999999', 'amount': '10', 'uuid': 'u1'}
        form.update(overrides)
        return self.client.post('/payment', data=form)

    def deposit(self, **overrides):
        """Submit a deposit form from a saved external account"""
        form = {'account': SAVED_ACCOUNT, 'amount': '10', 'uuid': 'u2'}
        form.update(overrides)
        return self.client.post('/deposit', data=form)

    def sent(self, call):
        """The JSON body of a mocked requests.post call"""
        return json.loads(call.kwargs['data'])

    def ledger_calls(self):
        """The mocked posts that went to ledgerwriter"""
        uri = self.app.config['TRANSACTIONS_URI']
        return [c for c in self.post.call_args_list
                if c.kwargs['url'] == uri]

    def contact_calls(self):
        """The mocked posts that went to the contacts service"""
        uri = self.app.config['CONTACTS_URI']
        return [c for c in self.post.call_args_list
                if c.kwargs['url'].startswith(uri)]


class TestAuthentication(HandlerTestCase):
    """Only signed in users can move money"""

    def test_payment_without_token_is_unauthorized(self):
        """no token cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        resp = self.payment()
        self.assertEqual(resp.status_code, 401)
        self.post.assert_not_called()

    def test_deposit_without_token_is_unauthorized(self):
        """no token cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        resp = self.deposit()
        self.assertEqual(resp.status_code, 401)
        self.post.assert_not_called()

    def test_payment_with_invalid_token_is_unauthorized(self):
        """a token that fails verification gives 401 and nothing is sent"""
        with patch('frontend.jwt.decode',
                   side_effect=jwt.exceptions.InvalidTokenError):
            resp = self.payment()
        self.assertEqual(resp.status_code, 401)
        self.post.assert_not_called()

    def test_deposit_with_invalid_token_is_unauthorized(self):
        """a token that fails verification gives 401 and nothing is sent"""
        with patch('frontend.jwt.decode',
                   side_effect=jwt.exceptions.InvalidTokenError):
            resp = self.deposit()
        self.assertEqual(resp.status_code, 401)
        self.post.assert_not_called()


class TestPayment(HandlerTestCase):
    """/payment"""

    def test_success_redirects_to_home_with_message(self):
        """a 201 from ledgerwriter gives a 303 to /home"""
        resp = self.payment()
        self.assertEqual(resp.status_code, 303)
        location = resp.headers['Location']
        self.assertIn('/home', location)
        self.assertIn('msg=Payment+successful', location)

    def test_success_waits_for_propagation(self):
        """the handler pauses so balance and history catch up"""
        self.payment()
        self.sleep.assert_called_once_with(0.25)

    def test_sends_transaction_to_ledgerwriter(self):
        """the amount is converted to cents and the accounts come from the token"""
        self.payment(amount='12.34')
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.sent(calls[0]), {
            'fromAccountNum': ACCOUNT_ID,
            'fromRoutingNum': LOCAL_ROUTING,
            'toAccountNum': '9999999999',
            'toRoutingNum': LOCAL_ROUTING,
            'amount': 1234,
            'uuid': 'u1',
        })
        self.assertEqual(calls[0].kwargs['headers']['Authorization'],
                         'Bearer abc')
        self.assertEqual(self.contact_calls(), [])

    def test_whole_amount_is_converted_to_cents(self):
        """10 dollars is 1000 cents"""
        self.payment(amount='10')
        self.assertEqual(self.sent(self.ledger_calls()[0])['amount'], 1000)

    def test_new_contact_is_saved_before_paying(self):
        """paying a new account with a label adds the contact first"""
        resp = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='Alice')
        self.assertEqual(resp.status_code, 303)
        contacts = self.contact_calls()
        self.assertEqual(len(contacts), 1)
        self.assertTrue(contacts[0].kwargs['url'].endswith('/testuser'))
        self.assertEqual(self.sent(contacts[0]), {
            'label': 'Alice',
            'account_num': '7777777777',
            'routing_num': LOCAL_ROUTING,
            'is_external': False,
        })
        ledger = self.ledger_calls()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(self.sent(ledger[0])['toAccountNum'], '7777777777')
        # the contact is posted before the transaction
        self.assertEqual(self.post.call_args_list[0], contacts[0])

    def test_new_account_without_label_is_not_saved(self):
        """no label means the account is paid but no contact is created"""
        resp = self.payment(account_num='add',
                            contact_account_num='7777777777')
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(self.contact_calls(), [])
        self.assertEqual(self.sent(self.ledger_calls()[0])['toAccountNum'],
                         '7777777777')

    def test_rejected_contact_stops_the_payment(self):
        """if the contact cannot be saved the money is not sent"""
        self.post.return_value = backend_response(400, 'duplicate contact')
        resp = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='Alice')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Payment failed: duplicate contact',
                      resp.get_data(as_text=True))
        self.assertEqual(self.ledger_calls(), [])

    def test_new_account_without_number_is_rejected(self):
        """choosing 'add' without an account number is a missing field"""
        resp = self.payment(account_num='add')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Payment failed: missing form field',
                      resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_missing_fields_are_rejected(self):
        """each required form field is checked"""
        for field in ('account_num', 'amount', 'uuid'):
            with self.subTest(field=field):
                form = {'account_num': '9999999999', 'amount': '10',
                        'uuid': 'u1'}
                del form[field]
                resp = self.client.post('/payment', data=form)
                self.assertEqual(resp.status_code, 400)
                self.assertIn('Payment failed: missing form field',
                              resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_invalid_amounts_are_rejected(self):
        """amounts that are not numbers give 400 and send nothing"""
        for amount in ('', 'abc', '1,5', 'NaN'):
            with self.subTest(amount=amount):
                resp = self.payment(amount=amount)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(
                    f'Payment failed: {amount} is not a valid number',
                    resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_failure_does_not_wait_or_redirect(self):
        """errors render the page directly and skip the propagation delay"""
        self.post.return_value = backend_response(400, 'nope')
        resp = self.payment()
        self.assertNotIn('Location', resp.headers)
        self.sleep.assert_not_called()

    def test_ledger_reason_is_escaped(self):
        """the backend's reason is shown as text, not markup"""
        self.post.return_value = backend_response(400, '<script>x</script>')
        resp = self.payment()
        body = resp.get_data(as_text=True)
        self.assertNotIn('<script>x</script>', body)
        self.assertIn('&lt;script&gt;x&lt;/script&gt;', body)

    def test_ledger_not_found_is_a_client_error(self):
        """any 4xx from ledgerwriter gives 400 with its reason"""
        self.post.return_value = backend_response(404, 'unknown account')
        resp = self.payment()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Payment failed: unknown account',
                      resp.get_data(as_text=True))

    def test_ledger_timeout_is_a_bad_gateway(self):
        """a timeout gives 502"""
        self.post.side_effect = requests.exceptions.Timeout
        resp = self.payment()
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Payment failed', resp.get_data(as_text=True))
        self.assertIn('text-danger', resp.get_data(as_text=True))

    def test_contacts_unreachable_is_a_bad_gateway(self):
        """the contacts service being down gives 502 and no payment"""
        self.post.side_effect = requests.exceptions.ConnectionError
        resp = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='Alice')
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(self.ledger_calls(), [])


class TestDeposit(HandlerTestCase):
    """/deposit"""

    def new_account(self, **overrides):
        """Submit a deposit from a new external account"""
        form = {'account': 'add', 'external_account_num': '1111111111',
                'external_routing_num': '123456789', 'amount': '10',
                'uuid': 'u2'}
        form.update(overrides)
        return self.client.post('/deposit', data=form)

    def test_success_redirects_to_home_with_message(self):
        """a 201 from ledgerwriter gives a 303 to /home"""
        resp = self.deposit()
        self.assertEqual(resp.status_code, 303)
        location = resp.headers['Location']
        self.assertIn('/home', location)
        self.assertIn('msg=Deposit+successful', location)

    def test_success_waits_for_propagation(self):
        """the handler pauses so balance and history catch up"""
        self.deposit()
        self.sleep.assert_called_once_with(0.25)

    def test_saved_account_sends_transaction(self):
        """a saved contact is the source and the user's account the target"""
        self.deposit(amount='99.99')
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.sent(calls[0]), {
            'fromAccountNum': '5555555555',
            'fromRoutingNum': '123456789',
            'toAccountNum': ACCOUNT_ID,
            'toRoutingNum': LOCAL_ROUTING,
            'amount': 9999,
            'uuid': 'u2',
        })
        self.assertEqual(calls[0].kwargs['headers']['Authorization'],
                         'Bearer abc')
        self.assertEqual(self.contact_calls(), [])

    def test_new_external_account_is_saved_with_label(self):
        """a labelled new account is added as an external contact first"""
        resp = self.new_account(external_label='My other bank')
        self.assertEqual(resp.status_code, 303)
        contacts = self.contact_calls()
        self.assertEqual(len(contacts), 1)
        self.assertEqual(self.sent(contacts[0]), {
            'label': 'My other bank',
            'account_num': '1111111111',
            'routing_num': '123456789',
            'is_external': True,
        })
        ledger = self.ledger_calls()
        self.assertEqual(self.sent(ledger[0])['fromAccountNum'], '1111111111')
        self.assertEqual(self.post.call_args_list[0], contacts[0])

    def test_new_external_account_without_label_is_not_saved(self):
        """no label means no contact is created"""
        resp = self.new_account()
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(self.contact_calls(), [])
        self.assertEqual(len(self.ledger_calls()), 1)

    def test_rejected_contact_stops_the_deposit(self):
        """if the contact cannot be saved the deposit is not sent"""
        self.post.return_value = backend_response(400, 'bad contact')
        resp = self.new_account(external_label='My other bank')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Deposit failed: bad contact',
                      resp.get_data(as_text=True))
        self.assertEqual(self.ledger_calls(), [])

    def test_local_routing_number_is_rejected_before_any_call(self):
        """depositing from the bank's own routing number is refused"""
        resp = self.new_account(external_routing_num=LOCAL_ROUTING,
                                external_label='Me')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Deposit failed: invalid routing number',
                      resp.get_data(as_text=True))
        self.post.assert_not_called()
        self.sleep.assert_not_called()

    def test_new_account_missing_fields_are_rejected(self):
        """account number and routing number are required for a new account"""
        for field in ('external_account_num', 'external_routing_num'):
            with self.subTest(field=field):
                form = {'account': 'add', 'external_account_num': '1',
                        'external_routing_num': '123456789', 'amount': '10',
                        'uuid': 'u2'}
                del form[field]
                resp = self.client.post('/deposit', data=form)
                self.assertEqual(resp.status_code, 400)
                self.assertIn('Deposit failed: missing form field',
                              resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_missing_fields_are_rejected(self):
        """account, amount and uuid are required"""
        for field in ('account', 'amount', 'uuid'):
            with self.subTest(field=field):
                form = {'account': SAVED_ACCOUNT, 'amount': '10',
                        'uuid': 'u2'}
                del form[field]
                resp = self.client.post('/deposit', data=form)
                self.assertEqual(resp.status_code, 400)
                self.assertIn('Deposit failed: missing form field',
                              resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_saved_account_missing_details_is_rejected(self):
        """a saved account without routing details is a missing field"""
        resp = self.deposit(account=json.dumps({'account_num': '1'}))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Deposit failed: missing form field',
                      resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_malformed_saved_account_is_rejected(self):
        """an account that is not JSON gives 400 and sends nothing"""
        resp = self.deposit(account='not json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Deposit failed', resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_invalid_amounts_are_rejected(self):
        """amounts that are not numbers give 400 and send nothing"""
        for amount in ('', 'abc', '1,5', 'NaN'):
            with self.subTest(amount=amount):
                resp = self.deposit(amount=amount)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(
                    f'Deposit failed: {amount} is not a valid number',
                    resp.get_data(as_text=True))
        self.post.assert_not_called()

    def test_ledger_rejection_shows_reason(self):
        """a 4xx from ledgerwriter gives 400 with its reason"""
        self.post.return_value = backend_response(400, 'amount too large')
        resp = self.deposit()
        self.assertEqual(resp.status_code, 400)
        body = resp.get_data(as_text=True)
        self.assertIn('Deposit failed: amount too large', body)
        self.assertIn('text-danger', body)
        self.assertNotIn('Location', resp.headers)
        self.sleep.assert_not_called()

    def test_ledger_server_error_is_a_bad_gateway(self):
        """a 5xx from ledgerwriter gives 502"""
        self.post.return_value = backend_response(500, 'boom')
        resp = self.deposit()
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Deposit failed: boom', resp.get_data(as_text=True))

    def test_ledger_timeout_is_a_bad_gateway(self):
        """a timeout gives 502 without exposing an exception message"""
        self.post.side_effect = requests.exceptions.Timeout('secret detail')
        resp = self.deposit()
        self.assertEqual(resp.status_code, 502)
        body = resp.get_data(as_text=True)
        self.assertIn('Deposit failed', body)
        self.assertNotIn('secret detail', body)

    def test_ledger_reason_is_escaped(self):
        """the backend's reason is shown as text, not markup"""
        self.post.return_value = backend_response(400, '<b>bad</b>')
        resp = self.deposit()
        body = resp.get_data(as_text=True)
        self.assertNotIn('<b>bad</b>', body)
        self.assertIn('&lt;b&gt;bad&lt;/b&gt;', body)


if __name__ == '__main__':
    unittest.main()
