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
Integration test for the currency_orders table, on the real accounts-db
(Postgres with the Bank of Anthos schema), reached through ACCOUNTS_DB_URI.
Not part of the unit test run.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

# pylint: disable=wrong-import-position
import orders

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
QUOTE = {'currency': 'EUR', 'amount': Decimal('100.00'),
         'market_rate': Decimal('0.80123456'),
         'customer_rate': Decimal('0.78120370'),
         'subtotal': Decimal('124.81'), 'fee': Decimal('3.12'),
         'delivery': Decimal('5.00'), 'total': Decimal('132.93')}


@pytest.fixture(name='db')
def fixture_db():
    """OrdersDb on the real database, as production constructs it"""
    uri = os.environ.get('ACCOUNTS_DB_URI')
    if not uri:
        pytest.fail('ACCOUNTS_DB_URI must point at the accounts-db database')
    clock = {'now': T0}
    store = orders.OrdersDb(uri, clock=lambda: clock['now'])
    store.test_clock = clock
    yield store
    with store.engine.begin() as conn:
        conn.execute(text("DELETE FROM currency_orders WHERE username LIKE 'it-%'"))


def test_order_lifecycle(db):
    """an order is stored, confirmed, read back with its locked values and advances"""
    user = {'user': 'it-' + uuid.uuid4().hex[:8], 'acct': '1011226111'}
    order_id = orders.new_order_id()
    db.create(order_id, user, QUOTE, '1 Main Street, Springfield')
    assert db.list_for(user['user']) == []   # not paid yet
    db.confirm(order_id)

    order = db.get_for(user['user'], order_id)
    assert order['status'] == 'Placed'
    assert order['customer_rate'] == QUOTE['customer_rate']
    assert order['total'] == QUOTE['total']
    assert order['address'] == '1 Main Street, Springfield'

    db.test_clock['now'] = T0 + timedelta(seconds=1000)
    assert db.get_for(user['user'], order_id)['status'] == 'Delivered'
    assert [o['order_id'] for o in db.list_for(user['user'])] == [order_id]


def test_orders_are_private(db):
    """another user cannot read the order"""
    owner = {'user': 'it-' + uuid.uuid4().hex[:8], 'acct': '1011226111'}
    order_id = orders.new_order_id()
    db.create(order_id, owner, QUOTE, '1 Main Street, Springfield')
    db.confirm(order_id)
    assert db.get_for('it-someone-else', order_id) is None
    assert db.list_for('it-someone-else') == []
