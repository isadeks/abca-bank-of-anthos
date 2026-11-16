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
Tests for optional two-factor sign-in (TOTP) in userservice
"""

import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open

import jwt

from userservice import totp
from userservice.userservice import create_app
from userservice.tests.constants import (
    EXAMPLE_USER,
    EXAMPLE_USER_REQUEST,
    EXAMPLE_PRIVATE_KEY,
    EXAMPLE_PUBLIC_KEY,
)

# RFC 6238 appendix B test secret ("12345678901234567890") and vectors
RFC_SECRET = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'


class TestTotp(unittest.TestCase):
    """The TOTP helpers"""

    def test_rfc6238_vectors(self):
        """6-digit codes match RFC 6238 (last six digits of the SHA-1 vectors)"""
        self.assertEqual(totp.totp_at(RFC_SECRET, 59), '287082')
        self.assertEqual(totp.totp_at(RFC_SECRET, 1111111109), '081804')
        self.assertEqual(totp.totp_at(RFC_SECRET, 2000000000), '279037')

    def test_verify_allows_drift_and_refuses_replay(self):
        """a neighbouring step is accepted once"""
        now = 1111111109
        code = totp.totp_at(RFC_SECRET, now - 30)
        step = totp.verify_totp(RFC_SECRET, code, now=now)
        self.assertIsNotNone(step)
        self.assertIsNone(totp.verify_totp(RFC_SECRET, code, now=now, last_step=step))
        self.assertIsNone(totp.verify_totp(RFC_SECRET, totp.totp_at(RFC_SECRET, now - 300),
                                           now=now))

    def test_verify_rejects_malformed_codes(self):
        """only 6 digits are valid"""
        for bad in ('', '12345', '1234567', 'abcdef', None):
            self.assertIsNone(totp.verify_totp(RFC_SECRET, bad, now=59))

    def test_secret_encryption_round_trip(self):
        """a stored secret is not readable without the key"""
        enc = totp.encrypt_secret(RFC_SECRET, b'key')
        self.assertNotIn(RFC_SECRET.encode(), enc)
        self.assertEqual(totp.decrypt_secret(enc, b'key'), RFC_SECRET)
        self.assertIsNone(totp.decrypt_secret(enc, b'other'))

    def test_recovery_codes(self):
        """8 distinct codes; hashing ignores case and dashes"""
        codes = totp.new_recovery_codes()
        self.assertEqual(len(set(codes)), 8)
        self.assertEqual(totp.hash_recovery_code(codes[0], b'k'),
                         totp.hash_recovery_code(codes[0].lower().replace('-', ' '), b'k'))
        self.assertNotIn(codes[0], totp.hash_recovery_code(codes[0], b'k'))

    def test_provisioning_uri(self):
        """the URI carries the secret and issuer"""
        uri = totp.provisioning_uri('ABC', 'jdoe', 'Bank of Anthos')
        self.assertTrue(uri.startswith('otpauth://totp/Bank%20of%20Anthos%3Ajdoe?secret=ABC'))
        self.assertIn('issuer=Bank%20of%20Anthos', uri)


class TestTwoFactor(unittest.TestCase):
    """The login, setup, enable and disable endpoints"""

    def setUp(self):
        with patch('userservice.userservice.open', mock_open(read_data='foo')):
            with patch('os.environ', {
                    'VERSION': '1',
                    'TOKEN_EXPIRY_SECONDS': '3600',
                    'PRIV_KEY_PATH': '1',
                    'PUB_KEY_PATH': '1',
                    'ENABLE_TRACING': 'false'}):
                with patch('userservice.userservice.UserDb') as mock_db:
                    self.db = mock_db.return_value
                    self.flask_app = create_app()
        self.flask_app.config['TESTING'] = True
        self.flask_app.config['PRIVATE_KEY'] = EXAMPLE_PRIVATE_KEY
        self.flask_app.config['PUBLIC_KEY'] = EXAMPLE_PUBLIC_KEY
        self.client = self.flask_app.test_client()
        self.db.get_user.return_value = EXAMPLE_USER.copy()
        # in-memory stand-in for the user_totp table
        self.rows = {}
        self.db.get_mfa.side_effect = lambda u: dict(self.rows[u]) if u in self.rows else None
        self.db.save_mfa.side_effect = self._save
        self.db.delete_mfa.side_effect = lambda u: self.rows.pop(u, None)
        patcher = patch('bcrypt.checkpw', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _save(self, username, values):
        row = self.rows.setdefault(username, {'recovery_hashes': []})
        row.update(values)

    def _session(self):
        token = jwt.encode({'user': 'jdoe', 'exp': datetime.utcnow() + timedelta(hours=1)},
                           EXAMPLE_PRIVATE_KEY, algorithm='RS256')
        return {'Authorization': 'Bearer ' + token}

    def _enable(self):
        """Turn 2FA on through the API; return (secret, recovery codes)"""
        secret = self.client.post('/2fa/setup', headers=self._session()).json['secret']
        code = totp.totp_at(secret, time.time())
        resp = self.client.post('/2fa/enable', data={'code': code}, headers=self._session())
        self.assertEqual(resp.status_code, 200)
        return secret, resp.json['recovery_codes']

    def _password_step(self):
        return self.client.get('/login', query_string=EXAMPLE_USER_REQUEST)

    def _next_code(self, secret):
        """A valid code for a step that has not been used yet"""
        step = self.rows['jdoe'].get('last_step') or 0
        return totp.totp_at(secret, max(time.time(), (step + 1) * totp.STEP_SECONDS))

    def test_login_without_2fa_is_unchanged(self):
        """no 2FA row: the password alone gives a JWT"""
        resp = self._password_step()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.json.keys()), ['token'])

    def test_login_with_pending_setup_is_unchanged(self):
        """a setup that was never confirmed does not lock the user out"""
        self.client.post('/2fa/setup', headers=self._session())
        self.assertEqual(self._password_step().status_code, 200)

    def test_endpoints_need_a_session(self):
        """no bearer token, no 2FA management"""
        for path in ('/2fa/setup', '/2fa/enable', '/2fa/disable'):
            self.assertEqual(self.client.post(path).status_code, 401)
        self.assertEqual(self.client.get('/2fa').status_code, 401)

    def test_setup_stores_the_secret_encrypted(self):
        """the stored secret is not the plain secret"""
        resp = self.client.post('/2fa/setup', headers=self._session())
        self.assertEqual(resp.status_code, 200)
        secret = resp.json['secret']
        self.assertIn(secret, resp.json['uri'])
        self.assertFalse(self.rows['jdoe']['enabled'])
        self.assertNotIn(secret.encode(), bytes(self.rows['jdoe']['secret_enc']))

    def test_enable_needs_the_right_code(self):
        """a wrong confirmation code keeps 2FA off"""
        self.client.post('/2fa/setup', headers=self._session())
        resp = self.client.post('/2fa/enable', data={'code': '000000'},
                                headers=self._session())
        self.assertIn(resp.status_code, (401,))
        self.assertFalse(self.rows['jdoe']['enabled'])

    def test_enable_returns_recovery_codes_stored_hashed(self):
        """8 codes are returned once and only hashes are stored"""
        _, codes = self._enable()
        self.assertEqual(len(codes), 8)
        stored = self.rows['jdoe']['recovery_hashes']
        self.assertEqual(len(stored), 8)
        for code in codes:
            self.assertNotIn(code, stored)
        status = self.client.get('/2fa', headers=self._session()).json
        self.assertEqual(status, {'enabled': True, 'recovery_codes_left': 8})

    def test_login_asks_for_second_factor_and_issues_jwt_after(self):
        """password -> 401 mfa_required, then token + code -> JWT"""
        secret, _ = self._enable()
        first = self._password_step()
        self.assertEqual(first.status_code, 401)
        self.assertTrue(first.json['mfa_required'])
        self.assertNotIn('token', first.json)
        resp = self.client.get('/login', query_string={
            'username': 'jdoe', 'mfa_token': first.json['mfa_token'],
            'code': self._next_code(secret)})
        self.assertEqual(resp.status_code, 200)
        claims = jwt.decode(resp.json['token'], EXAMPLE_PUBLIC_KEY, algorithms=['RS256'])
        self.assertEqual(claims['user'], 'jdoe')

    def test_mfa_token_is_not_a_session_token(self):
        """the intermediate token cannot be verified as an RS256 session"""
        self._enable()
        mfa_token = self._password_step().json['mfa_token']
        with self.assertRaises(jwt.InvalidTokenError):
            jwt.decode(mfa_token, EXAMPLE_PUBLIC_KEY, algorithms=['RS256'])
        resp = self.client.get('/2fa', headers={'Authorization': 'Bearer ' + mfa_token})
        self.assertEqual(resp.status_code, 401)

    def test_second_step_needs_a_valid_mfa_token(self):
        """a code alone, without the password step, is refused"""
        secret, _ = self._enable()
        resp = self.client.get('/login', query_string={
            'username': 'jdoe', 'mfa_token': 'junk', 'code': self._next_code(secret)})
        self.assertEqual(resp.status_code, 401)

    def test_wrong_code_is_refused(self):
        """a wrong code gives 401 and no token"""
        self._enable()
        mfa_token = self._password_step().json['mfa_token']
        resp = self.client.get('/login', query_string={
            'username': 'jdoe', 'mfa_token': mfa_token, 'code': '123456'})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(self.rows['jdoe']['failed_attempts'], 1)

    def test_totp_code_cannot_be_replayed(self):
        """the same code is refused the second time"""
        secret, _ = self._enable()
        code = self._next_code(secret)
        for expected in (200, 401):
            mfa_token = self._password_step().json['mfa_token']
            resp = self.client.get('/login', query_string={
                'username': 'jdoe', 'mfa_token': mfa_token, 'code': code})
            self.assertEqual(resp.status_code, expected)

    def test_recovery_code_works_once(self):
        """a recovery code signs in and is then used up"""
        _, codes = self._enable()
        for expected in (200, 401):
            mfa_token = self._password_step().json['mfa_token']
            resp = self.client.get('/login', query_string={
                'username': 'jdoe', 'mfa_token': mfa_token, 'code': codes[0]})
            self.assertEqual(resp.status_code, expected)
        self.assertEqual(len(self.rows['jdoe']['recovery_hashes']), 7)

    def test_wrong_codes_are_rate_limited(self):
        """after 5 wrong codes even the right one is refused with 429"""
        secret, _ = self._enable()
        mfa_token = self._password_step().json['mfa_token']
        for _ in range(5):
            resp = self.client.get('/login', query_string={
                'username': 'jdoe', 'mfa_token': mfa_token, 'code': '111111'})
            self.assertEqual(resp.status_code, 401)
        resp = self.client.get('/login', query_string={
            'username': 'jdoe', 'mfa_token': mfa_token, 'code': self._next_code(secret)})
        self.assertEqual(resp.status_code, 429)

    def test_lockout_expires(self):
        """once the lock has passed the right code works again"""
        secret, _ = self._enable()
        self.rows['jdoe']['locked_until'] = datetime.utcnow() - timedelta(seconds=1)
        mfa_token = self._password_step().json['mfa_token']
        resp = self.client.get('/login', query_string={
            'username': 'jdoe', 'mfa_token': mfa_token, 'code': self._next_code(secret)})
        self.assertEqual(resp.status_code, 200)

    def test_disable_needs_a_code(self):
        """a wrong code keeps 2FA on; a right one removes it"""
        secret, _ = self._enable()
        resp = self.client.post('/2fa/disable', data={'code': '123456'},
                                headers=self._session())
        self.assertEqual(resp.status_code, 401)
        self.assertIn('jdoe', self.rows)
        resp = self.client.post('/2fa/disable', data={'code': self._next_code(secret)},
                                headers=self._session())
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('jdoe', self.rows)
        self.assertEqual(self._password_step().status_code, 200)

    def test_setup_refused_while_enabled(self):
        """a second setup cannot replace an active secret"""
        self._enable()
        resp = self.client.post('/2fa/setup', headers=self._session())
        self.assertEqual(resp.status_code, 409)

    def test_codes_and_secrets_are_not_logged(self):
        """no log line contains the secret or a recovery code"""
        with self.assertLogs(self.flask_app.logger, level='DEBUG') as logs:
            self.flask_app.logger.info('start')
            secret, codes = self._enable()
            self.client.get('/login', query_string={
                'username': 'jdoe', 'mfa_token': 'x', 'code': codes[1]})
        text = '\n'.join(logs.output)
        self.assertNotIn(secret, text)
        self.assertNotIn(codes[0], text)
        self.assertNotIn(codes[1], text)


if __name__ == '__main__':
    unittest.main()
