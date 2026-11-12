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
cognito_auth wraps the Amazon Cognito user pool that owns the users'
credentials and issues the sign-in (ID) token.
"""

import os

import boto3
from botocore.exceptions import ClientError

# Claims of the Cognito ID token that carry the Bank of Anthos identity.
# See the "Token claim contract" section of the README.
ACCOUNT_ID_ATTRIBUTE = 'custom:acct'
DISPLAY_NAME_ATTRIBUTE = 'name'


class CognitoAuthError(Exception):
    """Base class of the errors raised by CognitoAuth."""


class InvalidCredentials(CognitoAuthError):
    """The password is wrong, or the user cannot sign in."""


class UnknownUser(CognitoAuthError):
    """The user does not exist in the user pool."""


class UserExists(CognitoAuthError):
    """A user with that username already exists in the user pool."""


class InvalidPassword(CognitoAuthError):
    """The password does not satisfy the user pool's password policy."""


class CognitoAuth:
    """Authenticates and creates users in one Cognito user pool.

    Params: user_pool_id - id of the user pool
            client_id - id of the app client (a public client, without a
                        secret, with the USER_PASSWORD_AUTH flow enabled)
            region - AWS region of the user pool
            client - optional boto3 'cognito-idp' client (for tests)
    """

    def __init__(self, user_pool_id, client_id, region, client=None):
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.client = client or boto3.client('cognito-idp', region_name=region)

    @classmethod
    def from_env(cls, environ=None):
        """Build from COGNITO_USER_POOL_ID, COGNITO_APP_CLIENT_ID and
        COGNITO_REGION (falling back to AWS_REGION).

        Raises: KeyError naming the first variable that is not set
        """
        environ = os.environ if environ is None else environ
        region = environ.get('COGNITO_REGION') or environ.get('AWS_REGION')
        if not region:
            raise KeyError('COGNITO_REGION')
        return cls(environ['COGNITO_USER_POOL_ID'],
                   environ['COGNITO_APP_CLIENT_ID'],
                   region)

    def authenticate(self, username, password):
        """Sign a user in and return Cognito's ID token (a JWT string).

        Raises: UnknownUser if the user does not exist
                InvalidCredentials if the password is wrong or the user
                    cannot complete a plain password sign-in
        """
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={'USERNAME': username, 'PASSWORD': password},
            )
        except ClientError as err:
            code = err.response['Error']['Code']
            if code == 'UserNotFoundException':
                raise UnknownUser('user {} does not exist'.format(username)) from err
            if code in ('NotAuthorizedException', 'UserNotConfirmedException',
                        'PasswordResetRequiredException'):
                raise InvalidCredentials('invalid login') from err
            raise
        result = response.get('AuthenticationResult')
        if not result or 'IdToken' not in result:
            # A challenge (e.g. NEW_PASSWORD_REQUIRED, MFA) instead of a token
            raise InvalidCredentials('invalid login')
        return result['IdToken']

    def create_user(self, username, password, accountid, display_name):
        """Create a confirmed user with a permanent password.

        The account id and display name are stored as the user's attributes
        so that they reach the ID token as claims.

        Raises: UserExists if the username is taken
                InvalidPassword if the password violates the pool's policy
        """
        try:
            self.client.admin_create_user(
                UserPoolId=self.user_pool_id,
                Username=username,
                UserAttributes=[
                    {'Name': ACCOUNT_ID_ATTRIBUTE, 'Value': accountid},
                    {'Name': DISPLAY_NAME_ATTRIBUTE, 'Value': display_name},
                ],
                MessageAction='SUPPRESS',
            )
        except ClientError as err:
            if err.response['Error']['Code'] == 'UsernameExistsException':
                raise UserExists('user {} already exists'.format(username)) from err
            raise
        try:
            self.client.admin_set_user_password(
                UserPoolId=self.user_pool_id,
                Username=username,
                Password=password,
                Permanent=True,
            )
        except ClientError as err:
            # Do not leave a user without a usable password behind
            self.delete_user(username)
            if err.response['Error']['Code'] == 'InvalidPasswordException':
                raise InvalidPassword(
                    err.response['Error'].get('Message') or 'invalid password') from err
            raise

    def delete_user(self, username):
        """Delete a user, ignoring one that does not exist."""
        try:
            self.client.admin_delete_user(
                UserPoolId=self.user_pool_id, Username=username)
        except ClientError as err:
            if err.response['Error']['Code'] != 'UserNotFoundException':
                raise
