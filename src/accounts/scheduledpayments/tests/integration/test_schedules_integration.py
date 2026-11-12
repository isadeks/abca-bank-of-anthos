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
Integration tests for the scheduled payments service against the real
accounts-db (Postgres with the Bank of Anthos schema): the tables of the
schema, ownership, the double-payment protection and the runner.
"""

import datetime
import logging
import threading
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import db
from signing import PaymentTokenSigner
from worker import PaymentRunner, payment_id

UTC = datetime.timezone.utc
D = datetime.date
LEASE = datetime.timedelta(minutes=5)
GIVE_UP = datetime.timedelta(minutes=50)
LOCAL_ROUTING_NUM = '883745000'


def at(day, hour=9):
    """A moment on the given date"""
    return datetime.datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def new_schedule(schedule_db, user, due=D(2026, 4, 7), frequency='weekly', amount=2500):
    """Store a schedule of this user, to a made-up recipient"""
    username, account = user
    return schedule_db.create_schedule({
        'username': username, 'from_account_num': account,
        'to_account_num': '1033623433', 'to_label': 'Alice',
        'amount_cents': amount, 'frequency': frequency,
        'anchor_day': due.day, 'next_payment_date': due})


def test_tables_come_from_the_accounts_schema(schedule_db):
    """The schema of accounts-db creates both tables with their constraints."""
    with schedule_db.engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"))}
    assert {'scheduled_payments', 'scheduled_payment_attempts'} <= tables


def test_created_schedule_is_listed_with_its_fields(schedule_db, user):
    """Every field, including the date, round-trips through Postgres."""
    created = new_schedule(schedule_db, user)

    listed = schedule_db.list_schedules(user[0])

    assert [s['schedule_id'] for s in listed] == [created['schedule_id']]
    assert listed[0]['next_payment_date'] == D(2026, 4, 7)
    assert listed[0]['amount_cents'] == 2500
    assert listed[0]['frequency'] == 'weekly'
    assert listed[0]['to_label'] == 'Alice'
    assert listed[0]['last_status'] is None


def test_schedules_are_per_user_and_cancel_is_owner_only(schedule_db, user, other_user):
    """Another user neither sees nor cancels a schedule."""
    created = new_schedule(schedule_db, user)

    assert schedule_db.list_schedules(other_user[0]) == []
    assert not schedule_db.cancel_schedule(other_user[0], created['schedule_id'])
    assert len(schedule_db.list_schedules(user[0])) == 1
    assert schedule_db.cancel_schedule(user[0], created['schedule_id'])
    assert schedule_db.list_schedules(user[0]) == []


def test_schedule_needs_an_existing_user(schedule_db):
    """The schedule is tied to a user of the bank."""
    with pytest.raises(IntegrityError):
        new_schedule(schedule_db, ('nobody_' + 'x' * 10, '1000000000'))


def test_database_refuses_invalid_values(schedule_db, user):
    """The schema checks the amount and the frequency as well."""
    with pytest.raises(IntegrityError):
        new_schedule(schedule_db, user, amount=0)
    with pytest.raises(IntegrityError):
        new_schedule(schedule_db, user, frequency='daily')


def test_a_due_date_can_be_claimed_only_once(schedule_db, user):
    """The second claim of the same (schedule, date) is refused."""
    schedule = new_schedule(schedule_db, user)
    args = (schedule['schedule_id'], D(2026, 4, 7), D(2026, 4, 14), at(D(2026, 4, 7)),
            LEASE, GIVE_UP)

    assert schedule_db.claim_attempt(*args) == db.CLAIMED
    assert schedule_db.claim_attempt(*args) == db.BUSY


def test_concurrent_claims_have_a_single_winner(schedule_db, user):
    """Runners racing for the same date: exactly one pays."""
    schedule = new_schedule(schedule_db, user)
    results = []

    def claim():
        results.append(schedule_db.claim_attempt(
            schedule['schedule_id'], D(2026, 4, 7), D(2026, 4, 14),
            at(D(2026, 4, 7)), LEASE, GIVE_UP))

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(db.CLAIMED) == 1
    assert set(results) <= {db.CLAIMED, db.BUSY}


def test_stale_claim_is_retried_then_given_up(schedule_db, user):
    """Time zones survive the round trip: a dead runner's claim is handed out
    again after the lease, and written off after the give up time."""
    schedule = new_schedule(schedule_db, user)
    first = at(D(2026, 4, 7))
    sid = schedule['schedule_id']
    assert schedule_db.claim_attempt(sid, D(2026, 4, 7), D(2026, 4, 14), first,
                                     LEASE, GIVE_UP) == db.CLAIMED

    soon = first + datetime.timedelta(minutes=2)
    later = first + datetime.timedelta(minutes=10)
    much_later = first + datetime.timedelta(hours=3)
    assert schedule_db.claim_attempt(sid, D(2026, 4, 7), D(2026, 4, 14), soon,
                                     LEASE, GIVE_UP) == db.BUSY
    assert schedule_db.claim_attempt(sid, D(2026, 4, 7), D(2026, 4, 14), later,
                                     LEASE, GIVE_UP) == db.CLAIMED
    assert schedule_db.claim_attempt(sid, D(2026, 4, 7), D(2026, 4, 14), much_later,
                                     LEASE, GIVE_UP) == db.DONE

    attempt = schedule_db.get_attempt(sid, D(2026, 4, 7))
    assert attempt['status'] == 'failed'
    current = schedule_db.list_schedules(user[0])[0]
    assert current['next_payment_date'] == D(2026, 4, 14)
    assert current['last_status'] == 'failed'


def make_runner(schedule_db, ledger):
    """A runner on the real database with the ledger mocked"""
    return PaymentRunner(
        schedule_db, PaymentTokenSigner(_private_key()),
        'http://ledgerwriter:8080/transactions', LOCAL_ROUTING_NUM,
        logging.getLogger('test'), post=ledger)


_KEY = []


def _private_key():
    if not _KEY:
        from Crypto.PublicKey import RSA  # pylint: disable=import-outside-toplevel
        _KEY.append(RSA.generate(2048).export_key().decode())
    return _KEY[0]


def test_runner_pays_a_due_schedule_once(schedule_db, user):
    """The payment is sent, recorded and the schedule moves a week on; a
    second runner on the same day pays nothing."""
    schedule = new_schedule(schedule_db, user)
    ledger = MagicMock(return_value=MagicMock(status_code=201, text='ok'))

    mine = {s['schedule_id'] for s in schedule_db.due_schedules(D(2026, 4, 7))}
    assert schedule['schedule_id'] in mine
    make_runner(schedule_db, ledger).run_once(now=at(D(2026, 4, 7)))
    make_runner(schedule_db, ledger).run_once(now=at(D(2026, 4, 7), hour=12))

    mine_calls = [c for c in ledger.call_args_list
                  if payment_id(schedule['schedule_id'], D(2026, 4, 7)) in c.kwargs['data']]
    assert len(mine_calls) == 1
    current = schedule_db.list_schedules(user[0])[0]
    assert current['next_payment_date'] == D(2026, 4, 14)
    assert current['last_status'] == 'succeeded'
    attempt = schedule_db.get_attempt(schedule['schedule_id'], D(2026, 4, 7))
    assert attempt['status'] == 'succeeded'


def test_runner_records_a_failure_and_moves_on(schedule_db, user):
    """An insufficient balance is kept with the schedule, not retried the same week."""
    schedule = new_schedule(schedule_db, user, frequency='monthly', due=D(2026, 1, 31))
    ledger = MagicMock(return_value=MagicMock(status_code=400, text='insufficient balance'))
    runner = make_runner(schedule_db, ledger)

    runner.run_once(now=at(D(2026, 1, 31)))
    runner.run_once(now=at(D(2026, 2, 10)))

    own = [c for c in ledger.call_args_list
           if payment_id(schedule['schedule_id'], D(2026, 1, 31)) in c.kwargs['data']]
    assert len(own) == 1
    current = schedule_db.list_schedules(user[0])[0]
    assert current['last_status'] == 'failed'
    assert current['last_error'] == 'insufficient balance'
    assert current['last_attempt_date'] == D(2026, 1, 31)
    assert current['next_payment_date'] == D(2026, 2, 28)


def test_runner_never_runs_a_cancelled_schedule(schedule_db, user):
    """Cancelled schedules are not paid."""
    schedule = new_schedule(schedule_db, user)
    schedule_db.cancel_schedule(user[0], schedule['schedule_id'])
    ledger = MagicMock(return_value=MagicMock(status_code=201, text='ok'))

    make_runner(schedule_db, ledger).run_once(now=at(D(2026, 4, 7)))

    assert not [c for c in ledger.call_args_list
                if payment_id(schedule['schedule_id'], D(2026, 4, 7)) in c.kwargs['data']]
