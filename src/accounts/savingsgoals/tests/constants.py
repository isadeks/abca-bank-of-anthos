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

"""Constants and helpers used in the savings goals tests"""
import jwt
from Crypto.PublicKey import RSA

_KEY = RSA.generate(2048)
EXAMPLE_PRIVATE_KEY = _KEY.export_key()
EXAMPLE_PUBLIC_KEY = _KEY.publickey().export_key()
EXAMPLE_USER = "foo"
EXAMPLE_ACCT = "1234512345"


def make_token(user=EXAMPLE_USER):
    """A signed token for the given user"""
    return jwt.encode({"user": user, "acct": EXAMPLE_ACCT},
                      EXAMPLE_PRIVATE_KEY, algorithm="RS256")


def auth_headers():
    """Authorization header of the example user"""
    return {"Authorization": "Bearer " + make_token()}
