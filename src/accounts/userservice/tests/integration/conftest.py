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
Fixtures for the userservice integration tests.

These run against the real accounts-db (Postgres with the Bank of Anthos
schema), reached through the ACCOUNTS_DB_URI environment variable.
They are not part of the unit test run (see scripts/test-changed.sh).
"""

import importlib.util
import os
import sys
import uuid

import pytest
from Crypto.PublicKey import RSA
from sqlalchemy import text

# Import the service's modules the way production does (`from db import UserDb`).
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

# pylint: disable=wrong-import-position
from db import UserDb


def load_service():
    """Load userservice.py from the service directory.

    The module shares its name with the directory that the unit tests import as
    a package (`userservice.userservice`), so it is loaded by path here.
    """
    spec = importlib.util.spec_from_file_location(
        'userservice_main', os.path.join(SERVICE_DIR, 'userservice.py'))
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
def key_files(tmp_path_factory):
    """A throwaway RSA key pair written to disk, like the mounted JWT keys."""
    key = RSA.generate(2048)
    directory = tmp_path_factory.mktemp('keys')
    priv = directory / 'jwtRS256.key'
    pub = directory / 'jwtRS256.key.pub'
    priv.write_bytes(key.export_key())
    pub.write_bytes(key.publickey().export_key())
    return str(priv), str(pub)


@pytest.fixture
def users_db(accounts_db_uri):
    """UserDb on the real database, as production constructs it."""
    return UserDb(accounts_db_uri)


@pytest.fixture
def client(monkeypatch, accounts_db_uri, key_files):
    """Flask test client of a userservice wired to the real database."""
    priv, pub = key_files
    monkeypatch.setenv('VERSION', 'integration-test')
    monkeypatch.setenv('TOKEN_EXPIRY_SECONDS', '3600')
    monkeypatch.setenv('PRIV_KEY_PATH', priv)
    monkeypatch.setenv('PUB_KEY_PATH', pub)
    monkeypatch.setenv('ENABLE_TRACING', 'false')
    monkeypatch.setenv('ACCOUNTS_DB_URI', accounts_db_uri)
    app = load_service().create_app()
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture
def new_username(users_db):
    """Generate a unique username and remove its user row afterwards."""
    username = 'it_' + uuid.uuid4().hex[:10]
    yield username
    with users_db.engine.connect() as conn:
        conn.execute(text('DELETE FROM users WHERE username = :u'), u=username)
