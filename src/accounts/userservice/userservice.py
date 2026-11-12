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
import logging
import os
import sys
import re

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

import cognito_auth
from db import UserDb
from trace_logging import add_trace_context

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

        Generates a unique accountid, creates the user in the Cognito user
        pool (which owns the credentials) and stores the profile and the
        accountid in the accounts database.

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

            if auth is None:
                app.logger.error("Error creating new user: Cognito is not configured")
                return 'authentication is not configured', 500

            accountid = users_db.generate_accountid()

            # Cognito owns the credentials: create the user in the user pool,
            # with the account id and display name as attributes (token claims)
            app.logger.debug("Creating the user in Cognito.")
            auth.create_user(
                req['username'],
                req['password'],
                accountid,
                '{} {}'.format(req['firstname'], req['lastname']),
            )

            # The profile stays in the accounts database. The password hash
            # column is required by the schema but no longer used: Cognito
            # holds the only copy of the credentials.
            user_data = {
                'accountid': accountid,
                'username': req['username'],
                'passhash': b'',
                'firstname': req['firstname'],
                'lastname': req['lastname'],
                'birthday': req['birthday'],
                'timezone': req['timezone'],
                'address': req['address'],
                'state': req['state'],
                'zip': req['zip'],
                'ssn': req['ssn'],
            }
            app.logger.debug("Adding user to the database")
            try:
                users_db.add_user(user_data)
            except SQLAlchemyError:
                # Do not leave a Cognito user without a profile
                auth.delete_user(req['username'])
                raise
            app.logger.info("Successfully created user.")

        except UserWarning as warn:
            app.logger.error("Error creating new user: %s", str(warn))
            return str(warn), 400
        except (NameError, cognito_auth.UserExists) as err:
            app.logger.error("Error creating new user: %s", str(err))
            return str(err), 409
        except cognito_auth.InvalidPassword as err:
            app.logger.error("Error creating new user: %s", str(err))
            return str(err), 400
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
        """Login a user through Cognito and return its ID token

        Fails if username doesn't exist or the password is wrong

        The token's lifetime is configured on the Cognito app client.

        request fields:
        - username
        - password
        """
        app.logger.debug('Sanitizing login input.')
        username = bleach.clean(request.args.get('username') or '')
        password = bleach.clean(request.args.get('password') or '')

        if auth is None:
            app.logger.error('Error logging in: Cognito is not configured')
            return 'authentication is not configured', 500

        try:
            app.logger.debug('Authenticating against Cognito.')
            token = auth.authenticate(username, password)
            app.logger.info('Login Successful.')
            return jsonify({'token': token}), 200
        except cognito_auth.UnknownUser as err:
            app.logger.error('Error logging in: %s', str(err))
            return str(err), 404
        except cognito_auth.InvalidCredentials as err:
            app.logger.error('Error logging in: %s', str(err))
            return str(err), 401

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

    # Cognito user pool that owns the credentials and issues the ID token
    # (COGNITO_USER_POOL_ID, COGNITO_APP_CLIENT_ID, COGNITO_REGION)
    try:
        auth = cognito_auth.CognitoAuth.from_env()
    except KeyError as err:
        # Keep the service up (probes, version) but refuse logins and signups
        auth = None
        app.logger.critical("Cognito is not configured: %s is not set", err)

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
