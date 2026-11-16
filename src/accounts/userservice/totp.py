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
Helpers for optional two-factor sign-in: TOTP (RFC 6238), recovery codes and
encryption of the shared secret at rest.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

STEP_SECONDS = 30
DIGITS = 6
RECOVERY_CODE_COUNT = 8
# Alphabet without look-alike characters (0/O, 1/I)
_RECOVERY_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def new_secret():
    """A random 160-bit base32 TOTP secret"""
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii')


def _hotp(secret, counter):
    key = base64.b32decode(secret, casefold=True)
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def totp_at(secret, timestamp):
    """The TOTP code for the given unix time"""
    return _hotp(secret, int(timestamp // STEP_SECONDS))


def verify_totp(secret, code, now=None, last_step=None, window=1):
    """Check a 6-digit code, allowing +-window time steps of clock drift.

    A step that was already accepted (last_step) is refused, so a code
    cannot be replayed.

    Return: the matching time step, or None if the code is not valid
    """
    if not isinstance(code, str) or len(code) != DIGITS or not code.isdigit():
        return None
    now = time.time() if now is None else now
    current = int(now // STEP_SECONDS)
    matched = None
    for step in range(current - window, current + window + 1):
        if hmac.compare_digest(_hotp(secret, step), code):
            matched = step
    if matched is None or (last_step is not None and matched <= last_step):
        return None
    return matched


def provisioning_uri(secret, username, issuer):
    """otpauth:// URI that authenticator apps read from a QR code"""
    label = quote('{}:{}'.format(issuer, username), safe='')
    return 'otpauth://totp/{}?secret={}&issuer={}&digits={}&period={}'.format(
        label, secret, quote(issuer, safe=''), DIGITS, STEP_SECONDS)


def new_recovery_codes():
    """Return: RECOVERY_CODE_COUNT one-time codes like 'ABCDE-FGHJK'"""
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = ''.join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        codes.append(raw[:5] + '-' + raw[5:])
    return codes


def normalize_recovery_code(code):
    """Upper-case a recovery code and drop spaces and dashes"""
    return ''.join(c for c in str(code).upper() if c not in ' -')


def hash_recovery_code(code, key):
    """Keyed hash of a recovery code (they are random, so a fast hash is fine)"""
    return hmac.new(key, normalize_recovery_code(code).encode('utf-8'),
                    hashlib.sha256).hexdigest()


def _fernet(key_material):
    digest = hashlib.sha256(b'totp-secret|' + key_material).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret, key_material):
    """Encrypt a TOTP secret for storage"""
    return _fernet(key_material).encrypt(secret.encode('ascii'))


def decrypt_secret(token, key_material):
    """Return: the TOTP secret, or None if it cannot be decrypted"""
    try:
        return _fernet(key_material).decrypt(bytes(token)).decode('ascii')
    except InvalidToken:
        return None


def derive_key(key_material, purpose):
    """A purpose-specific key derived from the service's private key"""
    return hashlib.sha256(purpose.encode('ascii') + b'|' + key_material).digest()
