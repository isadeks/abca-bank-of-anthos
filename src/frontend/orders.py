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
Foreign currency orders: the stored order data (a table in accounts-db),
and the status an order has reached. There is no real courier in a demo
bank, so an order advances through its statuses as time passes.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (create_engine, MetaData, Table, Column, String,
                        Numeric, DateTime, select, update, delete)

PENDING = 'Payment pending'
STATUSES = ['Placed', 'Preparing', 'Out for delivery', 'Delivered']
# seconds after the order was placed at which each status is reached
DEFAULT_STEP_SECONDS = (0, 60, 180, 300)


def status_index(placed_at, now, step_seconds=DEFAULT_STEP_SECONDS):
    """Index in STATUSES of the status an order placed at `placed_at` has reached at `now`"""
    elapsed = (now - placed_at).total_seconds()
    reached = 0
    for index, after in enumerate(step_seconds):
        if elapsed >= after:
            reached = index
    return reached


def timeline(placed_at, now, step_seconds=DEFAULT_STEP_SECONDS):
    """
    The status timeline of an order: a list of dicts with the status,
    when it is/was reached, and whether it is reached, current.
    """
    current = status_index(placed_at, now, step_seconds)
    return [{'status': name,
             'at': placed_at + timedelta(seconds=step_seconds[i]),
             'reached': i <= current,
             'current': i == current}
            for i, name in enumerate(STATUSES)]


def new_order_id():
    """A new unique order id (also used as the ledger transaction uuid)"""
    return str(uuid.uuid4())


class OrdersDb:
    """Stores currency orders in the currency_orders table of accounts-db"""

    def __init__(self, uri, step_seconds=DEFAULT_STEP_SECONDS,
                 clock=lambda: datetime.now(timezone.utc)):
        self.engine = create_engine(uri)
        self.step_seconds = step_seconds
        self.clock = clock
        self.orders = Table(
            'currency_orders', MetaData(),
            Column('order_id', String(36), primary_key=True),
            Column('username', String(64), nullable=False, index=True),
            Column('account_id', String(10), nullable=False),
            Column('currency', String(3), nullable=False),
            Column('amount', Numeric(14, 2), nullable=False),
            Column('market_rate', Numeric(18, 8), nullable=False),
            Column('customer_rate', Numeric(18, 8), nullable=False),
            Column('subtotal', Numeric(14, 2), nullable=False),
            Column('fee', Numeric(14, 2), nullable=False),
            Column('delivery', Numeric(14, 2), nullable=False),
            Column('total', Numeric(14, 2), nullable=False),
            Column('address', String(300), nullable=False),
            Column('status', String(32), nullable=False),
            Column('placed_at', DateTime(timezone=True), nullable=False),
        )
        self._ready = False

    def _ensure_table(self):
        """Creates the table if the database predates it"""
        if not self._ready:
            self.orders.metadata.create_all(self.engine)
            self._ready = True

    def create(self, order_id, user, quote, address):
        """
        Stores a new order awaiting payment. `quote` is a dict as returned
        by fx.calculate_quote plus 'currency' and 'amount'; the rates in it
        are the locked rates of the order.
        """
        self._ensure_table()
        with self.engine.begin() as conn:
            conn.execute(self.orders.insert().values(
                order_id=order_id, username=user['user'],
                account_id=user['acct'], currency=quote['currency'],
                amount=quote['amount'], market_rate=quote['market_rate'],
                customer_rate=quote['customer_rate'],
                subtotal=quote['subtotal'], fee=quote['fee'],
                delivery=quote['delivery'], total=quote['total'],
                address=address, status=PENDING, placed_at=self.clock()))

    def confirm(self, order_id):
        """The payment went through: the order is placed (now)"""
        with self.engine.begin() as conn:
            conn.execute(update(self.orders)
                         .where(self.orders.c.order_id == order_id)
                         .values(status=STATUSES[0], placed_at=self.clock()))

    def discard(self, order_id):
        """The payment failed: the order is removed"""
        with self.engine.begin() as conn:
            conn.execute(delete(self.orders)
                         .where(self.orders.c.order_id == order_id)
                         .where(self.orders.c.status == PENDING))

    def _advance(self, conn, row):
        """Moves a stored order to the status it has reached; returns it as a dict"""
        order = dict(row._mapping)
        if order['placed_at'].tzinfo is None:
            order['placed_at'] = order['placed_at'].replace(tzinfo=timezone.utc)
        reached = STATUSES[status_index(order['placed_at'], self.clock(),
                                        self.step_seconds)]
        if reached != order['status']:
            conn.execute(update(self.orders)
                         .where(self.orders.c.order_id == order['order_id'])
                         .values(status=reached))
            order['status'] = reached
        order['timeline'] = timeline(order['placed_at'], self.clock(),
                                     self.step_seconds)
        return order

    def list_for(self, username):
        """The user's placed orders, newest first, with their current status"""
        self._ensure_table()
        query = (select(self.orders)
                 .where(self.orders.c.username == username)
                 .where(self.orders.c.status != PENDING)
                 .order_by(self.orders.c.placed_at.desc()))
        with self.engine.begin() as conn:
            return [self._advance(conn, row) for row in conn.execute(query)]

    def get_for(self, username, order_id):
        """
        One placed order of the user, or None if there is no such order or
        it belongs to somebody else.
        """
        self._ensure_table()
        query = (select(self.orders)
                 .where(self.orders.c.order_id == order_id)
                 .where(self.orders.c.username == username)
                 .where(self.orders.c.status != PENDING))
        with self.engine.begin() as conn:
            row = conn.execute(query).first()
            return self._advance(conn, row) if row else None


