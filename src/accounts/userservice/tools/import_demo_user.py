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
One-off import of an existing accounts-db user (by default the demo user
`testuser`) into the Cognito user pool.

Cognito cannot import the bcrypt hashes of the accounts database, so the user
is created with a password given here. The user's account id and display name
are read from the accounts database and stored as the Cognito attributes that
become the ID token claims (see the README), so the user keeps its account.

Usage, from the userservice directory, with AWS credentials that may manage
the user pool:

    export ACCOUNTS_DB_URI=postgresql://... \\
           COGNITO_USER_POOL_ID=... COGNITO_APP_CLIENT_ID=... COGNITO_REGION=...
    python tools/import_demo_user.py                 # testuser / bankofanthos
    python tools/import_demo_user.py --username alice --password 's3cret!'

Running it again for a user that is already in the pool changes nothing.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pylint: disable=wrong-import-position
import cognito_auth

# The demo accounts all use this login password (see kubernetes-manifests/config.yaml)
DEMO_PASSWORD = 'bankofanthos'


def import_user(users_db, auth, username, password):
    """Create the accounts-db user `username` in the Cognito user pool.

    Params: users_db - a UserDb
            auth - a CognitoAuth
    Return: 'created' or 'exists'
    Raises: LookupError if the user is not in the accounts database
            cognito_auth.InvalidPassword if the password violates the pool's policy
    """
    user = users_db.get_user(username)
    if user is None:
        raise LookupError('user {} is not in the accounts database'.format(username))
    try:
        auth.create_user(
            username,
            password,
            user['accountid'].strip(),
            '{} {}'.format(user['firstname'], user['lastname']),
        )
    except cognito_auth.UserExists:
        return 'exists'
    return 'created'


def main(argv=None):
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n', maxsplit=1)[0])
    parser.add_argument('--username', default='testuser',
                        help='accounts-db user to import (default: testuser)')
    parser.add_argument('--password', default=DEMO_PASSWORD,
                        help='password to set in Cognito (default: the demo password)')
    args = parser.parse_args(argv)

    # pylint: disable=import-outside-toplevel
    from db import UserDb
    users_db = UserDb(os.environ['ACCOUNTS_DB_URI'])
    auth = cognito_auth.CognitoAuth.from_env()
    try:
        outcome = import_user(users_db, auth, args.username, args.password)
    except (LookupError, cognito_auth.InvalidPassword) as err:
        print('error: {}'.format(err), file=sys.stderr)
        return 1
    print('{}: {}'.format(args.username, 'created in the user pool'
                          if outcome == 'created' else 'already in the user pool, left as is'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
