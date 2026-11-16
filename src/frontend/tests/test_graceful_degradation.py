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
Tests that the frontend degrades gracefully when balancereader,
transactionhistory or ledgerwriter is down: the page still renders, a retry
is made once, and a span event and a counter report the fallback.
"""

import os
import unittest
from unittest.mock import MagicMock, patch, mock_open

import requests

import frontend
import resilience

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
    'BALANCES_API_ADDR': 'balancereader',
    'HISTORY_API_ADDR': 'transactionhistory',
    'CONTACTS_API_ADDR': 'contacts',
    'TRANSACTIONS_API_ADDR': 'ledgerwriter',
}
TOKEN_DATA = {'user': 'testuser', 'acct': '1234567890', 'name': 'Test'}
HISTORY = [{'fromAccountNum': '1234567890', 'toAccountNum': '9999999999',
            'fromRoutingNum': '883745000', 'toRoutingNum': '883745000',
            'amount': 500, 'timestamp': '2026-01-02T03:04:05.000000+0000'}]


def ok_response(payload):
    """A fake successful backend response"""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


class TestGracefulDegradation(unittest.TestCase):
    """The home page and transactions survive a backend outage"""

    def setUp(self):
        self.down = set()
        self.get_calls = []
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.requests.get', side_effect=requests.RequestException),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.sleep'),
            patch('resilience.time.sleep'),
            patch('api_call.get', side_effect=self.fake_get),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.span = MagicMock()
        self.counter = MagicMock()
        meter = MagicMock()
        meter.create_counter.return_value = self.counter
        fake_trace = MagicMock()
        fake_trace.get_current_span.return_value = self.span
        fake_metrics = MagicMock()
        fake_metrics.get_meter.return_value = meter
        for target, value in (('resilience.trace', fake_trace),
                              ('resilience.metrics', fake_metrics)):
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        self.post = patch('frontend.requests.post').start()
        self.addCleanup(patch.stopall)
        self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'abc')

    def fake_get(self, url, **_kwargs):
        """Stand in for the backends; those in self.down refuse connections"""
        self.get_calls.append(url)
        for backend in self.down:
            if f'//{backend}/' in url:
                raise requests.exceptions.ConnectionError('down')
        if '//balancereader/' in url:
            return ok_response(12345)
        if '//transactionhistory/' in url:
            return ok_response([dict(t) for t in HISTORY])
        return ok_response([])

    def fallback_backends(self):
        """Backends named in the fallback span events"""
        return [c.args[1]['backend'] for c in self.span.add_event.call_args_list
                if c.args[0] == resilience.FALLBACK_EVENT]

    def test_all_backends_up_no_fallback(self):
        """healthy backends: full page and no fallback telemetry"""
        resp = self.client.get('/home')
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('$123.45', body)
        self.assertNotIn('temporarily unavailable', body)
        self.span.add_event.assert_not_called()
        self.counter.add.assert_not_called()

    def test_balancereader_down(self):
        """no balance: the rest of the page renders with a notice"""
        self.down.add('balancereader')
        resp = self.client.get('/home')
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Balance temporarily unavailable', body)
        self.assertNotIn('History temporarily unavailable', body)
        self.assertIn('Transaction History', body)
        self.assertIn('<td', body)
        self.assertEqual(self.fallback_backends(), ['balance'])
        self.counter.add.assert_called_once()

    def test_transactionhistory_down(self):
        """no history: the table is replaced by a notice, balance stays"""
        self.down.add('transactionhistory')
        resp = self.client.get('/home')
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('History temporarily unavailable', body)
        self.assertIn('$123.45', body)
        self.assertNotIn('<table class="table table-sm', body)
        self.assertEqual(self.fallback_backends(), ['transaction_list'])
        self.counter.add.assert_called_once()

    def test_both_down(self):
        """balancereader and transactionhistory both down still renders"""
        self.down.update(['balancereader', 'transactionhistory'])
        resp = self.client.get('/home')
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Balance temporarily unavailable', body)
        self.assertIn('History temporarily unavailable', body)
        self.assertEqual(self.counter.add.call_count, 2)

    def test_backend_error_status_uses_fallback(self):
        """a 5xx from balancereader is a failure too, not a crash"""
        bad = MagicMock()
        bad.raise_for_status.side_effect = requests.exceptions.HTTPError('500')
        original = self.fake_get

        def get(url, **kwargs):
            if '//balancereader/' in url:
                return bad
            return original(url, **kwargs)
        with patch('api_call.get', side_effect=get):
            body = self.client.get('/home').get_data(as_text=True)
        self.assertIn('Balance temporarily unavailable', body)

    def test_failed_read_is_retried_once(self):
        """a down backend is called twice (one retry), not more"""
        self.down.add('balancereader')
        self.client.get('/home')
        balance_calls = [u for u in self.get_calls if '//balancereader/' in u]
        self.assertEqual(len(balance_calls), 2)
        resilience.time.sleep.assert_called_with(resilience.BACKOFF_SECONDS)

    def test_transient_failure_recovers_without_fallback(self):
        """one failure then success: normal page, no fallback emitted"""
        attempts = []
        original = self.fake_get

        def flaky(url, **kwargs):
            if '//balancereader/' in url and not attempts:
                attempts.append(url)
                raise requests.exceptions.Timeout('slow')
            return original(url, **kwargs)
        with patch('api_call.get', side_effect=flaky):
            body = self.client.get('/home').get_data(as_text=True)
        self.assertIn('$123.45', body)
        self.span.add_event.assert_not_called()

    def test_payment_with_ledgerwriter_down(self):
        """an unreachable ledgerwriter shows an error, never success"""
        self.post.side_effect = requests.exceptions.ConnectionError
        resp = self.client.post('/payment', data={
            'account_num': '9999999999', 'amount': '10', 'uuid': 'u1'})
        self.assertEqual(resp.status_code, 502)
        body = resp.get_data(as_text=True)
        self.assertIn('Payment failed', body)
        self.assertNotIn('Payment successful', body)
        self.assertEqual(self.post.call_count, 2)
        self.assertEqual(self.fallback_backends(), ['ledgerwriter'])
        self.counter.add.assert_called_once()

    def test_deposit_with_ledgerwriter_down(self):
        """a ledgerwriter timeout on deposit shows an error, never success"""
        self.post.side_effect = requests.exceptions.Timeout
        resp = self.client.post('/deposit', data={
            'account': 'add', 'external_account_num': '1111111111',
            'external_routing_num': '123456789', 'amount': '10', 'uuid': 'u2'})
        self.assertEqual(resp.status_code, 502)
        body = resp.get_data(as_text=True)
        self.assertIn('Deposit failed', body)
        self.assertNotIn('Deposit successful', body)
        self.assertEqual(self.fallback_backends(), ['ledgerwriter'])

    def test_ledgerwriter_server_error_is_reported(self):
        """a 5xx from ledgerwriter is a failure with fallback telemetry"""
        resp_500 = MagicMock()
        resp_500.status_code = 503
        resp_500.text = 'unavailable'
        resp_500.raise_for_status.side_effect = requests.exceptions.HTTPError
        self.post.return_value = resp_500
        resp = self.client.post('/payment', data={
            'account_num': '9999999999', 'amount': '10', 'uuid': 'u3'})
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Payment failed', resp.get_data(as_text=True))
        self.assertEqual(self.fallback_backends(), ['ledgerwriter'])


class TestRecordFallback(unittest.TestCase):
    """record_fallback emits a span event and increments the counter"""

    def test_emits_event_and_counter(self):
        span = MagicMock()
        meter = MagicMock()
        with patch('resilience.trace') as fake_trace, \
                patch('resilience.metrics') as fake_metrics:
            fake_trace.get_current_span.return_value = span
            fake_metrics.get_meter.return_value = meter
            resilience.record_fallback('balance', 'Timeout')
        attrs = {'backend': 'balance', 'reason': 'Timeout'}
        span.add_event.assert_called_once_with(resilience.FALLBACK_EVENT, attrs)
        meter.create_counter.assert_called_once()
        meter.create_counter.return_value.add.assert_called_once_with(1, attrs)


if __name__ == '__main__':
    unittest.main()
