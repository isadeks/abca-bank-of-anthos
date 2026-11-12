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
Short-lived payment tokens for the scheduled payments runner.

The runner submits a payment through the ledger on the customer's behalf, and
the ledger only accepts a token signed with the bank's key. This is the only
code in the service that touches the signing key, and it is deliberately
narrow:

- the token names exactly one customer (user and account), taken from the
  customer's own schedule;
- it carries no other claim and expires after at most MAX_TOKEN_TTL seconds,
  so a leaked token is useless almost at once;
- tokens are minted for one payment and never stored or returned by any route.
"""

import datetime
import re

import jwt

MAX_TOKEN_TTL = 60  # seconds
_ACCOUNT_RE = re.compile(r"\A[0-9]{10}\Z")


class PaymentTokenSigner:
    """Signs tokens for one customer at a time with the bank's private key."""

    def __init__(self, private_key, ttl_seconds=MAX_TOKEN_TTL):
        if not private_key:
            raise ValueError("a signing key is required")
        if not 0 < ttl_seconds <= MAX_TOKEN_TTL:
            raise ValueError(
                f"token lifetime must be 1 to {MAX_TOKEN_TTL} seconds")
        self._private_key = private_key
        self._ttl = datetime.timedelta(seconds=ttl_seconds)

    def __repr__(self):
        return "PaymentTokenSigner(ttl=%ss)" % self._ttl.total_seconds()

    def token_for(self, username, account_num, now=None):
        """A token that lets the ledger treat a request as coming from this
        customer, for the next few seconds."""
        if not username or not _ACCOUNT_RE.match(account_num or ""):
            raise ValueError("a username and a 10 digit account are required")
        now = now or datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "user": username,
            "acct": account_num,
            "name": username,
            "iat": now,
            "exp": now + self._ttl,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")
