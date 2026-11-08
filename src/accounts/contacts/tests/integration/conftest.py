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
Fixtures for the contacts integration tests.

These run against the real accounts-db (Postgres with the Bank of Anthos
schema), reached through the ACCOUNTS_DB_URI environment variable.
They are not part of the unit test run (see scripts/test-changed.sh).
"""

import importlib.util
import os
import sys
import uuid

import jwt
import pytest
from Crypto.PublicKey import RSA
from sqlalchemy import text

# Import the service's modules the way production does (`from db import ContactsDb`).
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

# pylint: disable=wrong-import-position
from db import ContactsDb

LOCAL_ROUTING_NUM = '883745000'  # the routing number of the demo bank


def load_service():
    """Load contacts.py from the service directory.

    The module shares its name with the module the unit tests import as a
    package (`contacts.contacts`), so it is loaded by path here.
    """
    spec = importlib.util.spec_from_file_location(
        'contacts_main', os.path.join(SERVICE_DIR, 'contacts.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='session')
def accounts_db_uri():
    """Connection string of the real accounts-db."""
    uri = os.environ.get('ACCOUNTS_DB_URI')
    if not uri:
        pytest.fail('ACCOUNTS_DB_URI must point at the accounts-db database')
    return uri


@pytest.fixture(scope='session')
def keys(tmp_path_factory):
    """A throwaway RSA key pair; the public half is written to disk like the mounted key."""
    key = RSA.generate(2048)
    pub = tmp_path_factory.mktemp('keys') / 'jwtRS256.key.pub'
    pub.write_bytes(key.publickey().export_key())
    return {'private': key.export_key().decode(), 'public_path': str(pub)}


@pytest.fixture
def contacts_db(accounts_db_uri):
    """ContactsDb on the real database, as production constructs it."""
    return ContactsDb(accounts_db_uri)


@pytest.fixture
def client(monkeypatch, accounts_db_uri, keys):
    """Flask test client of a contacts service wired to the real database."""
    monkeypatch.setenv('VERSION', 'integration-test')
    monkeypatch.setenv('LOCAL_ROUTING_NUM', LOCAL_ROUTING_NUM)
    monkeypatch.setenv('PUB_KEY_PATH', keys['public_path'])
    monkeypatch.setenv('ENABLE_TRACING', 'false')
    monkeypatch.setenv('ACCOUNTS_DB_URI', accounts_db_uri)
    app = load_service().create_app()
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture
def user(contacts_db):
    """Insert a user (contacts reference users by username) and clean up afterwards.

    Returns the username and account id.
    """
    username = 'it_' + uuid.uuid4().hex[:10]
    accountid = str(int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000)
    with contacts_db.engine.connect() as conn:
        conn.execute(
            text(
                'INSERT INTO users (accountid, username, passhash, firstname, lastname, '
                'birthday, timezone, address, state, zip, ssn) VALUES '
                "(:acct, :user, :hash, 'Integration', 'Test', '1990-02-03', '-5', "
                "'1 Test Street', 'NY', '10004', '123-45-6789')"
            ),
            acct=accountid, user=username, hash=b'not-a-real-hash')
    yield username, accountid
    with contacts_db.engine.connect() as conn:
        conn.execute(text('DELETE FROM contacts WHERE username = :u'), u=username)
        conn.execute(text('DELETE FROM users WHERE username = :u'), u=username)


@pytest.fixture
def auth_header(keys, user):
    """Authorization header for the fixture user, signed like userservice does."""
    username, accountid = user
    token = jwt.encode({'user': username, 'acct': accountid}, keys['private'], algorithm='RS256')
    return {'Authorization': 'Bearer ' + token}
