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
Tests for the short-lived payment tokens: what they say, how long they last,
and that the signing key is kept to the signer.
"""

import datetime
import unittest

import jwt

from signing import MAX_TOKEN_TTL, PaymentTokenSigner
from scheduledpayments.tests import helpers

NOW = datetime.datetime(2026, 4, 7, 9, 0, tzinfo=datetime.timezone.utc)


class TestPaymentTokens(unittest.TestCase):
    """PaymentTokenSigner"""

    def setUp(self):
        self.signer = PaymentTokenSigner(helpers.PRIVATE_KEY)

    def decode(self, token, **kwargs):
        """Verify a token like the ledger does, with the public key"""
        return jwt.decode(token, helpers.PUBLIC_KEY, algorithms="RS256", **kwargs)

    def test_token_is_verifiable_with_the_public_key(self):
        """the ledger accepts it: RS256 with the bank's key"""
        token = self.signer.token_for("testuser", helpers.ACCOUNT)
        claims = self.decode(token)
        self.assertEqual(claims["user"], "testuser")
        self.assertEqual(claims["acct"], helpers.ACCOUNT)

    def test_token_names_one_customer_and_nothing_else(self):
        """only the claims the ledger needs"""
        claims = self.decode(self.signer.token_for("testuser", helpers.ACCOUNT))
        self.assertEqual(sorted(claims),
                         ["acct", "exp", "iat", "name", "user"])

    def test_token_lives_for_one_minute(self):
        """short-lived by default"""
        claims = self.decode(
            self.signer.token_for("testuser", helpers.ACCOUNT, now=NOW),
            options={"verify_exp": False})
        self.assertEqual(claims["exp"] - claims["iat"], 60)

    def test_expired_token_is_refused(self):
        """a token minted in the past can't be used now"""
        token = self.signer.token_for("testuser", helpers.ACCOUNT, now=NOW)
        with self.assertRaises(jwt.exceptions.ExpiredSignatureError):
            self.decode(token)

    def test_lifetime_cannot_be_longer_than_the_maximum(self):
        """no way to ask for a long-lived token"""
        for ttl in (MAX_TOKEN_TTL + 1, 3600, 0, -1):
            with self.subTest(ttl=ttl):
                with self.assertRaises(ValueError):
                    PaymentTokenSigner(helpers.PRIVATE_KEY, ttl)
        PaymentTokenSigner(helpers.PRIVATE_KEY, MAX_TOKEN_TTL)

    def test_needs_a_key_a_user_and_an_account(self):
        """incomplete input is refused instead of signing a wrong token"""
        with self.assertRaises(ValueError):
            PaymentTokenSigner("")
        for user, account in (("", helpers.ACCOUNT), ("testuser", ""),
                              ("testuser", "123"), ("testuser", None),
                              ("testuser", "12345678901")):
            with self.subTest(user=user, account=account):
                with self.assertRaises(ValueError):
                    self.signer.token_for(user, account)

    def test_signer_does_not_reveal_the_key(self):
        """printing or logging the signer shows no key material"""
        self.assertNotIn("PRIVATE KEY", repr(self.signer))
        self.assertNotIn("PRIVATE KEY", str(self.signer))

    def test_app_does_not_keep_the_key_in_its_config(self):
        """the key is handed to the signer only"""
        app, _ = helpers.build_app(runner_enabled=True)
        try:
            for value in app.config.values():
                self.assertNotIn("PRIVATE KEY", str(value))
        finally:
            app.config["RUNNER_STOP"].set()


if __name__ == "__main__":
    unittest.main()
