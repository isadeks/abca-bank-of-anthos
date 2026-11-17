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
Unit tests for foreign currency orders: the status timeline, the order
store (on in-memory SQLite) and the order routes with the backends mocked.
"""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import jwt
import requests

import orders
from test_fx import rate_response
from test_payment_deposit_handlers import (HandlerTestCase, backend_response,
                                           ACCOUNT_ID)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
ADDRESS = '1 Main Street, Springfield'
QUOTE = {'currency': 'EUR', 'amount': Decimal('100.00'),
         'market_rate': Decimal('0.8'), 'customer_rate': Decimal('0.78'),
         'subtotal': Decimal('125.00'), 'fee': Decimal('3.13'),
         'delivery': Decimal('5.00'), 'total': Decimal('133.13')}


class Clock:
    """A settable clock"""

    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


class TestTimeline(unittest.TestCase):
    """Status moves with time"""

    def test_status_over_time(self):
        """each status is reached after its delay"""
        expected = {0: 0, 59: 0, 60: 1, 179: 1, 180: 2, 299: 2, 300: 3,
                    10000: 3}
        for seconds, index in expected.items():
            self.assertEqual(
                orders.status_index(T0, T0 + timedelta(seconds=seconds)),
                index, seconds)

    def test_timeline_marks_reached_and_current(self):
        """the timeline lists the four statuses in order"""
        steps = orders.timeline(T0, T0 + timedelta(seconds=100))
        self.assertEqual([s['status'] for s in steps], orders.STATUSES)
        self.assertEqual([s['reached'] for s in steps],
                         [True, True, False, False])
        self.assertEqual([s['current'] for s in steps],
                         [False, True, False, False])


class TestOrdersDb(unittest.TestCase):
    """The store"""

    def setUp(self):
        self.clock = Clock()
        self.db = orders.OrdersDb('sqlite://', clock=self.clock)
        self.user = {'user': 'alice', 'acct': '1111111111'}

    def place(self, order_id='o1', user=None):
        """Stores and confirms an order"""
        self.db.create(order_id, user or self.user, QUOTE, ADDRESS)
        self.db.confirm(order_id)

    def test_pending_orders_are_hidden(self):
        """an order awaiting payment is not listed or readable"""
        self.db.create('o1', self.user, QUOTE, ADDRESS)
        self.assertEqual(self.db.list_for('alice'), [])
        self.assertIsNone(self.db.get_for('alice', 'o1'))

    def test_discard_removes_pending(self):
        """a failed payment leaves nothing behind"""
        self.db.create('o1', self.user, QUOTE, ADDRESS)
        self.db.discard('o1')
        self.db.create('o1', self.user, QUOTE, ADDRESS)   # id free again

    def test_discard_keeps_placed(self):
        """a placed order cannot be discarded"""
        self.place()
        self.db.discard('o1')
        self.assertIsNotNone(self.db.get_for('alice', 'o1'))

    def test_status_advances(self):
        """reading the order later shows a later status"""
        self.place()
        self.assertEqual(self.db.get_for('alice', 'o1')['status'], 'Placed')
        self.clock.now = T0 + timedelta(seconds=70)
        self.assertEqual(self.db.get_for('alice', 'o1')['status'], 'Preparing')
        self.clock.now = T0 + timedelta(seconds=400)
        self.assertEqual(self.db.list_for('alice')[0]['status'], 'Delivered')

    def test_locked_values(self):
        """the stored order keeps the locked rate and amounts"""
        self.place()
        order = self.db.get_for('alice', 'o1')
        self.assertEqual(Decimal(order['customer_rate']), Decimal('0.78'))
        self.assertEqual(Decimal(order['total']), Decimal('133.13'))
        self.assertEqual(order['address'], ADDRESS)

    def test_ownership(self):
        """only the owner can read an order"""
        self.place()
        self.assertIsNone(self.db.get_for('bob', 'o1'))
        self.assertEqual(self.db.list_for('bob'), [])

    def test_list_newest_first(self):
        """the list is newest first"""
        self.place('o1')
        self.clock.now = T0 + timedelta(seconds=5)
        self.place('o2')
        self.assertEqual([o['order_id'] for o in self.db.list_for('alice')],
                         ['o2', 'o1'])


class TestOrderRoutes(HandlerTestCase):
    """The order routes"""

    def setUp(self):
        super().setUp()
        # frontend and fx share requests.get: one mock answers both
        self.fx_get = patch('frontend.requests.get',
                            side_effect=self.answer).start()
        self.rate = rate_response(0.8)
        self.cents = 100000
        self.clock = Clock()
        self.db = orders.OrdersDb('sqlite://', clock=self.clock)
        self.app.config['ORDERS_DB'] = self.db
        self.addCleanup(patch.stopall)

    def answer(self, *args, **kwargs):
        """The rate source or the balancereader"""
        if 'params' in kwargs:
            if isinstance(self.rate, Exception):
                raise self.rate
            return self.rate
        resp = MagicMock()
        resp.json.return_value = self.cents
        return resp

    def balance(self, cents):
        """Sets the balance the balancereader mock returns"""
        self.cents = cents

    def order(self, **overrides):
        """Submits the order form"""
        form = {'currency': 'EUR', 'amount': '100', 'address': ADDRESS}
        form.update(overrides)
        return self.client.post('/foreign-currency/order', data=form)

    def test_place_order(self):
        """a paid order is stored, debited through the ledger and shown"""
        resp = self.order()
        self.assertEqual(resp.status_code, 303)
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1)
        sent = self.sent(calls[0])
        self.assertEqual(sent['amount'], 13313)
        self.assertEqual(sent['fromAccountNum'], ACCOUNT_ID)
        self.assertEqual(sent['toAccountNum'], '9999900001')
        stored = self.db.list_for('testuser')
        self.assertEqual(len(stored), 1)
        self.assertEqual(sent['uuid'], stored[0]['order_id'])
        self.assertIn('/currency-orders/' + stored[0]['order_id'],
                      resp.headers['Location'])
        page = self.client.get(f'/currency-orders/{stored[0]["order_id"]}')
        html = page.get_data(as_text=True)
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="order-timeline"', html)
        self.assertIn('1 USD = 0.7800 EUR', html)
        self.assertIn(ADDRESS, html)

    def test_rate_locked(self):
        """a later rate change does not change the stored order"""
        self.order()
        self.rate = rate_response(0.5)
        order = self.db.list_for('testuser')[0]
        self.assertEqual(Decimal(order['customer_rate']), Decimal('0.78'))

    def test_insufficient_balance(self):
        """no order and no payment when the balance can't cover the total"""
        self.balance(13312)
        resp = self.order()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Insufficient balance', resp.get_data(as_text=True))
        self.assertEqual(self.ledger_calls(), [])
        self.assertEqual(self.db.list_for('testuser'), [])

    def test_exact_balance(self):
        """a balance equal to the total is enough"""
        self.balance(13313)
        self.assertEqual(self.order().status_code, 303)

    def test_ledger_rejects(self):
        """a rejected payment leaves no order"""
        self.post.return_value = backend_response(400, 'Insufficient balance')
        resp = self.order()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Payment failed', resp.get_data(as_text=True))
        self.assertEqual(self.db.list_for('testuser'), [])

    def test_ledger_down(self):
        """an unreachable ledger leaves no order"""
        self.post.side_effect = requests.exceptions.ConnectionError('x')
        resp = self.order()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(self.db.list_for('testuser'), [])

    def test_invalid_input(self):
        """bad input is rejected before anything is charged"""
        for bad in ({'currency': 'XXX'}, {'amount': '-1'}, {'amount': '1.234'},
                    {'address': ''}, {'address': 'short'},
                    {'address': 'x' * 301}):
            resp = self.order(**bad)
            self.assertEqual(resp.status_code, 400, bad)
        self.assertEqual(self.ledger_calls(), [])

    def test_rate_unavailable(self):
        """no order without a rate"""
        self.rate = requests.exceptions.ConnectionError('x')
        self.assertEqual(self.order().status_code, 503)
        self.assertEqual(self.ledger_calls(), [])

    def test_requires_login(self):
        """no valid token redirects to login for every route"""
        with patch('frontend.jwt.decode', side_effect=jwt.InvalidTokenError):
            for resp in (self.order(),
                         self.client.get('/currency-orders'),
                         self.client.get('/currency-orders/abc')):
                self.assertEqual(resp.status_code, 302)
                self.assertIn('/login', resp.headers['Location'])
        self.assertEqual(self.ledger_calls(), [])

    def test_list(self):
        """the list shows the user's orders and their status"""
        html = self.client.get('/currency-orders').get_data(as_text=True)
        self.assertIn('id="orders-empty"', html)
        self.order()
        self.clock.now = T0 + timedelta(seconds=70)
        html = self.client.get('/currency-orders').get_data(as_text=True)
        self.assertIn('id="orders-table"', html)
        self.assertIn('Preparing', html)

    def test_other_users_order_is_not_found(self):
        """an order of another user gives 404 on the detail page"""
        self.db.create('o9', {'user': 'bob', 'acct': '2222222222'}, QUOTE,
                       ADDRESS)
        self.db.confirm('o9')
        self.assertEqual(self.client.get('/currency-orders/o9').status_code, 404)
        self.assertNotIn('o9', self.client.get('/currency-orders')
                         .get_data(as_text=True))
        self.assertEqual(self.client.get('/currency-orders/nope').status_code, 404)

    def test_no_database(self):
        """without a database the pages say so"""
        self.app.config['ORDERS_DB'] = None
        self.assertEqual(self.order().status_code, 503)
        self.assertEqual(self.client.get('/currency-orders').status_code, 503)
        self.assertEqual(self.client.get('/currency-orders/x').status_code, 503)


if __name__ == '__main__':
    unittest.main()
