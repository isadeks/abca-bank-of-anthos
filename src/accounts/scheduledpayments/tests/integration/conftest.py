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
Fixtures for the scheduled payments integration tests.

These run against the real accounts-db (Postgres with the Bank of Anthos
schema), reached through the ACCOUNTS_DB_URI environment variable.
They are not part of the unit test run (see scripts/test-changed.sh).
"""

import os
import sys
import uuid

import pytest
from sqlalchemy import text

# Import the service's modules the way production does (`from db import ScheduleDb`).
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

# pylint: disable=wrong-import-position
from db import ScheduleDb


@pytest.fixture(scope='session')
def accounts_db_uri():
    """Connection string of the real accounts-db."""
    uri = os.environ.get('ACCOUNTS_DB_URI')
    if not uri:
        pytest.fail('ACCOUNTS_DB_URI must point at the accounts-db database')
    return uri


@pytest.fixture
def schedule_db(accounts_db_uri):
    """ScheduleDb on the real database, as production constructs it."""
    schedule_db = ScheduleDb(accounts_db_uri)
    schedule_db.create_tables()
    return schedule_db


def _new_user(schedule_db):
    username = 'it_' + uuid.uuid4().hex[:10]
    accountid = str(int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000)
    with schedule_db.engine.begin() as conn:
        conn.execute(
            text(
                'INSERT INTO users (accountid, username, passhash, firstname, lastname, '
                'birthday, timezone, address, state, zip, ssn) VALUES '
                "(:acct, :user, :hash, 'Integration', 'Test', '1990-02-03', '-5', "
                "'1 Test Street', 'NY', '10004', '123-45-6789')"
            ),
            acct=accountid, user=username, hash=b'not-a-real-hash')
    return username, accountid


def _drop_user(schedule_db, username):
    with schedule_db.engine.begin() as conn:
        conn.execute(text(
            'DELETE FROM scheduled_payment_attempts WHERE schedule_id IN '
            '(SELECT schedule_id FROM scheduled_payments WHERE username = :u)'),
            u=username)
        conn.execute(text('DELETE FROM scheduled_payments WHERE username = :u'), u=username)
        conn.execute(text('DELETE FROM users WHERE username = :u'), u=username)


@pytest.fixture
def user(schedule_db):
    """Insert a user (schedules reference users by username) and clean up afterwards.

    Returns the username and account id.
    """
    username, accountid = _new_user(schedule_db)
    yield username, accountid
    _drop_user(schedule_db, username)


@pytest.fixture
def other_user(schedule_db):
    """A second user, to check that schedules stay private."""
    username, accountid = _new_user(schedule_db)
    yield username, accountid
    _drop_user(schedule_db, username)
