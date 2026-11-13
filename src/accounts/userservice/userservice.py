# Copyright 2021 Google LLC
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
Userservice manages user account creation, user login, and related tasks
"""

import atexit
from datetime import datetime, timedelta
import logging
import os
import sys
import re

import bcrypt
import jwt
from flask import Flask, jsonify, request
import bleach
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.propagate import set_global_textmap
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from db import UserDb
from trace_logging import add_trace_context

# Label of the account every user gets at sign-up
PRIMARY_ACCOUNT_LABEL = 'Checking'
# Most accounts (sign-up account included) a user may have
MAX_ACCOUNTS = 5
# Same rule as contact labels: 1-30 alphanumerics and spaces, not starting with a space
ACCOUNT_LABEL_PATTERN = re.compile(r'\A[0-9a-zA-Z][0-9a-zA-Z ]{0,29}\Z')

def create_app():
    """Flask application factory to create instances
    of the Userservice Flask App
    """
    app = Flask(__name__)

    # Disabling unused-variable for lines with route decorated functions
    # as pylint thinks they are unused
    # pylint: disable=unused-variable

    @app.route('/version', methods=['GET'])
    def version():
        """
        Service version endpoint
        """
        return app.config['VERSION'], 200

    @app.route('/ready', methods=['GET'])
    def readiness():
        """
        Readiness probe
        """
        return 'ok', 200

    @app.route('/users', methods=['POST'])
    def create_user():
        """Create a user record.

        Fails if that username already exists.

        Generates a unique accountid.

        request fields:
        - username
        - password
        - password-repeat
        - firstname
        - lastname
        - birthday
        - timezone
        - address
        - state
        - zip
        - ssn
        """
        try:
            app.logger.debug('Sanitizing input.')
            req = {k: bleach.clean(v) for k, v in request.form.items()}
            __validate_new_user(req)
            # Check if user already exists
            if users_db.get_user(req['username']) is not None:
                raise NameError('user {} already exists'.format(req['username']))

            # Create password hash with salt
            app.logger.debug("Creating password hash.")
            password = req['password']
            salt = bcrypt.gensalt()
            passhash = bcrypt.hashpw(password.encode('utf-8'), salt)

            accountid = users_db.generate_accountid()

            # Create user data to be added to the database
            user_data = {
                'accountid': accountid,
                'username': req['username'],
                'passhash': passhash,
                'firstname': req['firstname'],
                'lastname': req['lastname'],
                'birthday': req['birthday'],
                'timezone': req['timezone'],
                'address': req['address'],
                'state': req['state'],
                'zip': req['zip'],
                'ssn': req['ssn'],
            }
            # Add user_data to database
            app.logger.debug("Adding user to the database")
            users_db.add_user(user_data)
            app.logger.info("Successfully created user.")

        except UserWarning as warn:
            app.logger.error("Error creating new user: %s", str(warn))
            return str(warn), 400
        except NameError as err:
            app.logger.error("Error creating new user: %s", str(err))
            return str(err), 409
        except SQLAlchemyError as err:
            app.logger.error("Error creating new user: %s", str(err))
            return 'failed to create user', 500

        return jsonify({}), 201

    def __validate_new_user(req):
        app.logger.debug('validating create user request: %s', str(req))
        # Check if required fields are filled
        fields = (
            'username',
            'password',
            'password-repeat',
            'firstname',
            'lastname',
            'birthday',
            'timezone',
            'address',
            'state',
            'zip',
            'ssn',
        )
        if any(f not in req for f in fields):
            raise UserWarning('missing required field(s)')
        if any(not bool(req[f] or req[f].strip()) for f in fields):
            raise UserWarning('missing value for input field(s)')

        # Verify username contains only 2-15 alphanumeric or underscore characters
        if not re.match(r"\A[a-zA-Z0-9_]{2,15}\Z", req['username']):
            raise UserWarning('username must contain 2-15 alphanumeric characters or underscores')
        # Check if passwords match
        if not req['password'] == req['password-repeat']:
            raise UserWarning('passwords do not match')

    @app.route('/login', methods=['GET'])
    def login():
        """Login a user and return a JWT token

        Fails if username doesn't exist or password doesn't match hash

        token expiry time determined by environment variable

        request fields:
        - username
        - password
        """
        app.logger.debug('Sanitizing login input.')
        username = bleach.clean(request.args.get('username'))
        password = bleach.clean(request.args.get('password'))

        # Get user data
        try:
            app.logger.debug('Getting the user data.')
            user = users_db.get_user(username)
            if user is None:
                raise LookupError('user {} does not exist'.format(username))

            # Validate the password
            app.logger.debug('Validating the password.')
            if not bcrypt.checkpw(password.encode('utf-8'), user['passhash']):
                raise PermissionError('invalid login')

            now = datetime.utcnow()
            exp_time = now + timedelta(seconds=app.config['EXPIRY_SECONDS'])
            app.logger.debug('Creating jwt token.')
            token = __make_token(user, user['accountid'], now, exp_time)
            app.logger.info('Login Successful.')
            return jsonify({'token': token}), 200

        except LookupError as err:
            app.logger.error('Error logging in: %s', str(err))
            return str(err), 404
        except PermissionError as err:
            app.logger.error('Error logging in: %s', str(err))
            return str(err), 401
        except SQLAlchemyError as err:
            app.logger.error('Error logging in: %s', str(err))
            return 'failed to retrieve user information', 500

    def __make_token(user, accountid, issued_at, expires_at):
        """Sign a token for a user acting on one of their accounts"""
        payload = {
            'user': user['username'],
            'acct': accountid,
            'name': '{} {}'.format(user['firstname'], user['lastname']),
            'iat': issued_at,
            'exp': expires_at,
        }
        return jwt.encode(payload, app.config['PRIVATE_KEY'], algorithm='RS256')

    def __authenticate(username):
        """Verify the bearer token of the request and that it belongs to username.

        Return: the token claims
        Raises: PermissionError if the token is missing, invalid or someone else's
        """
        auth_header = request.headers.get('Authorization')
        if auth_header is None or not auth_header.startswith('Bearer '):
            raise PermissionError('authentication denied')
        try:
            claims = jwt.decode(jwt=auth_header.split('Bearer ')[1],
                                key=app.config['PUBLIC_KEY'],
                                algorithms='RS256')
        except jwt.exceptions.InvalidTokenError as err:
            raise PermissionError('authentication denied') from err
        if claims.get('user') != username:
            raise PermissionError('authentication denied')
        return claims

    def __list_accounts(user):
        """All accounts of a user, the sign-up account first"""
        accounts = [{'accountid': user['accountid'],
                     'label': PRIMARY_ACCOUNT_LABEL,
                     'is_primary': True}]
        for account in users_db.get_accounts(user['username']):
            accounts.append({'accountid': account['accountid'],
                             'label': account['label'],
                             'is_primary': False})
        return accounts

    @app.route('/accounts/<username>', methods=['GET'])
    def get_accounts(username):
        """List the accounts of a user

        Requires a bearer token of that user.
        Return: a JSON list of {accountid, label, is_primary}, sign-up account first
        """
        try:
            __authenticate(username)
            user = users_db.get_user(username)
            if user is None:
                raise LookupError('user {} does not exist'.format(username))
            return jsonify(__list_accounts(user)), 200
        except PermissionError as err:
            return str(err), 401
        except LookupError as err:
            return str(err), 404
        except SQLAlchemyError as err:
            app.logger.error('Error listing accounts: %s', str(err))
            return 'failed to retrieve accounts', 500

    @app.route('/accounts/<username>', methods=['POST'])
    def create_account(username):
        """Open an additional account for a user

        Requires a bearer token of that user. Generates a unique accountid.

        request fields:
        - label
        """
        try:
            __authenticate(username)
            label = bleach.clean(request.form.get('label', '')).strip()
            if not ACCOUNT_LABEL_PATTERN.match(label):
                raise UserWarning('invalid account label: use 1-30 letters, '
                                  'numbers and spaces')
            user = users_db.get_user(username)
            if user is None:
                raise LookupError('user {} does not exist'.format(username))
            accounts = __list_accounts(user)
            if len(accounts) >= MAX_ACCOUNTS:
                raise UserWarning('at most {} accounts are allowed'.format(MAX_ACCOUNTS))
            if any(a['label'].lower() == label.lower() for a in accounts):
                raise NameError('an account with that label already exists')
            accountid = users_db.generate_accountid()
            users_db.add_account(username, accountid, label)
            app.logger.info('Opened a new account.')
            return jsonify({'accountid': accountid,
                            'label': label,
                            'is_primary': False}), 201
        except PermissionError as err:
            return str(err), 401
        except UserWarning as warn:
            return str(warn), 400
        except LookupError as err:
            return str(err), 404
        except NameError as err:
            return str(err), 409
        except SQLAlchemyError as err:
            app.logger.error('Error opening account: %s', str(err))
            return 'failed to open account', 500

    @app.route('/accounts/<username>/token', methods=['POST'])
    def switch_account(username):
        """Issue a token that acts on another of the user's accounts

        Requires a bearer token of that user. The new token expires when the
        presented one does, so switching does not extend the session.

        request fields:
        - accountid
        """
        try:
            claims = __authenticate(username)
            accountid = request.form.get('accountid', '')
            user = users_db.get_user(username)
            if user is None:
                raise LookupError('user {} does not exist'.format(username))
            if not any(a['accountid'] == accountid for a in __list_accounts(user)):
                raise LookupError('account {} does not exist'.format(accountid))
            token = __make_token(user, accountid,
                                 claims['iat'], claims['exp'])
            return jsonify({'token': token}), 200
        except PermissionError as err:
            return str(err), 401
        except LookupError as err:
            return str(err), 404
        except SQLAlchemyError as err:
            app.logger.error('Error switching account: %s', str(err))
            return 'failed to switch account', 500

    @atexit.register
    def _shutdown():
        """Executed when web app is terminated."""
        app.logger.info("Stopping userservice.")

    # Set up logger
    app.logger.handlers = logging.getLogger('gunicorn.error').handlers
    app.logger.setLevel(logging.getLogger('gunicorn.error').level)
    # Put the trace id and span id on every line, for the app logger and for the
    # database helpers that log through it (they share gunicorn's handlers)
    add_trace_context(logging.getLogger('gunicorn.error'), app.logger)
    app.logger.info('Starting userservice.')

    # Set up tracing and export spans over OTLP to the OpenTelemetry collector.
    if os.environ['ENABLE_TRACING'] == "true":
        app.logger.info("✅ Tracing enabled.")
        # The endpoint, service name and resource attributes (including
        # k8s.namespace.name) come from the standard OTEL_* environment
        # variables, read by the SDK and the exporter.
        trace.set_tracer_provider(TracerProvider())
        otlp_exporter = OTLPSpanExporter()
        trace.get_tracer_provider().add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
        # W3C trace context (traceparent) between services
        set_global_textmap(TraceContextTextMapPropagator())
        FlaskInstrumentor().instrument_app(app)
    else:
        app.logger.info("🚫 Tracing disabled.")

    app.config['VERSION'] = os.environ.get('VERSION')
    app.config['EXPIRY_SECONDS'] = int(os.environ.get('TOKEN_EXPIRY_SECONDS'))
    app.config['PRIVATE_KEY'] = open(os.environ.get('PRIV_KEY_PATH'), 'r').read()
    app.config['PUBLIC_KEY'] = open(os.environ.get('PUB_KEY_PATH'), 'r').read()

    # Configure database connection
    try:
        users_db = UserDb(os.environ.get("ACCOUNTS_DB_URI"), app.logger)
    except OperationalError:
        app.logger.critical("users_db database connection failed")
        sys.exit(1)
    return app


if __name__ == "__main__":
    # Create an instance of flask server when called directly
    USERSERVICE = create_app()
    USERSERVICE.run()
