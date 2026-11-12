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
In-memory stand-in for the boto3 'cognito-idp' client, answering the calls
userservice makes the way Cognito does (including its error codes).
"""

from botocore.exceptions import ClientError


def _error(code, message='', operation='Operation'):
    return ClientError({'Error': {'Code': code, 'Message': message}}, operation)


class FakeCognitoClient:
    """Keeps users in a dict: username -> {'password', 'attributes'}."""

    MIN_PASSWORD_LENGTH = 6

    def __init__(self):
        self.users = {}

    def initiate_auth(self, ClientId, AuthFlow, AuthParameters):
        # pylint: disable=invalid-name
        assert AuthFlow == 'USER_PASSWORD_AUTH'
        username = AuthParameters['USERNAME']
        user = self.users.get(username)
        if user is None:
            raise _error('UserNotFoundException', 'User does not exist.', 'InitiateAuth')
        if user['password'] != AuthParameters['PASSWORD']:
            raise _error('NotAuthorizedException', 'Incorrect username or password.',
                         'InitiateAuth')
        return {'AuthenticationResult': {'IdToken': 'id-token-for-' + username,
                                         'AccessToken': 'access-token',
                                         'RefreshToken': 'refresh-token'}}

    def admin_create_user(self, UserPoolId, Username, UserAttributes, MessageAction):
        # pylint: disable=invalid-name,unused-argument
        if Username in self.users:
            raise _error('UsernameExistsException', 'User account already exists.',
                         'AdminCreateUser')
        self.users[Username] = {
            'password': None,
            'attributes': {a['Name']: a['Value'] for a in UserAttributes},
        }

    def admin_set_user_password(self, UserPoolId, Username, Password, Permanent):
        # pylint: disable=invalid-name,unused-argument
        if len(Password) < self.MIN_PASSWORD_LENGTH:
            raise _error('InvalidPasswordException', 'Password did not conform with policy.',
                         'AdminSetUserPassword')
        self.users[Username]['password'] = Password

    def admin_delete_user(self, UserPoolId, Username):
        # pylint: disable=invalid-name,unused-argument
        if Username not in self.users:
            raise _error('UserNotFoundException', 'User does not exist.', 'AdminDeleteUser')
        del self.users[Username]
