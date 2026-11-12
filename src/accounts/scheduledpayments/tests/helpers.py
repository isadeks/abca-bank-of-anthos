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
Shared helpers for the scheduled payments tests: throwaway signing keys,
tokens, and an app wired to an in-memory database.
"""

import datetime
import os
import tempfile
from unittest.mock import MagicMock, patch

import jwt
from sqlalchemy.pool import StaticPool
from Crypto.PublicKey import RSA

from scheduledpayments.scheduledpayments import create_app
from db import ScheduleDb  # flat, like the service itself

LOCAL_ROUTING = "883745000"
USER = "testuser"
ACCOUNT = "1011226111"
ALICE = {"label": "Alice", "account_num": "1033623433",
         "routing_num": LOCAL_ROUTING, "is_external": False}
BOB = {"label": "Bob", "account_num": "1055757655",
       "routing_num": LOCAL_ROUTING, "is_external": False}
EXTERNAL = {"label": "Bank", "account_num": "1234567890",
            "routing_num": "123456789", "is_external": True}

_KEY = RSA.generate(2048)
PRIVATE_KEY = _KEY.export_key().decode()
PUBLIC_KEY = _KEY.publickey().export_key().decode()
OTHER_PRIVATE_KEY = RSA.generate(2048).export_key().decode()


def make_db():
    """A ScheduleDb on a private in-memory database"""
    sched_db = ScheduleDb("sqlite://", poolclass=StaticPool,
                          connect_args={"check_same_thread": False})
    sched_db.create_tables()
    return sched_db


def token_for(user=USER, account=ACCOUNT, key=PRIVATE_KEY, **claims):
    """A login token like the one userservice issues"""
    payload = {"user": user, "acct": account, "name": user.title(),
               "iat": datetime.datetime.now(datetime.timezone.utc),
               "exp": datetime.datetime.now(datetime.timezone.utc)
               + datetime.timedelta(hours=1)}
    payload.update(claims)
    return jwt.encode(payload, key, algorithm="RS256")


def auth(user=USER, account=ACCOUNT, **claims):
    """Request headers of a signed in customer"""
    return {"Authorization": "Bearer " + token_for(user, account, **claims),
            "content-type": "application/json"}


def contacts_response(contacts, status=200):
    """A fake answer of the contacts service"""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = contacts
    if status >= 400:
        import requests  # pylint: disable=import-outside-toplevel
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            str(status))
    return resp


def build_app(sched_db=None, runner_enabled=False):
    """The Flask app on a throwaway database; returns (app, db)."""
    sched_db = sched_db or make_db()
    tmp = tempfile.mkdtemp()
    pub = os.path.join(tmp, "publickey")
    priv = os.path.join(tmp, "privatekey")
    with open(pub, "w") as handle:
        handle.write(PUBLIC_KEY)
    with open(priv, "w") as handle:
        handle.write(PRIVATE_KEY)
    env = {
        "VERSION": "1",
        "PUB_KEY_PATH": pub,
        "PRIV_KEY_PATH": priv,
        "ENABLE_TRACING": "false",
        "ENABLE_RUNNER": "true" if runner_enabled else "false",
        "RUNNER_INTERVAL_SECONDS": "3600",
        "ACCOUNTS_DB_URI": "sqlite://",
        "CONTACTS_API_ADDR": "contacts:8080",
        "TRANSACTIONS_API_ADDR": "ledgerwriter:8080",
        "LOCAL_ROUTING_NUM": LOCAL_ROUTING,
    }
    with patch.dict(os.environ, env), patch(
            "scheduledpayments.scheduledpayments.ScheduleDb",
            return_value=sched_db):
        app = create_app()
    app.config["TESTING"] = True
    return app, sched_db
