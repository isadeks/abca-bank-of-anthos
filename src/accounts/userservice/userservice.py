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

import totp
from db import UserDb
from trace_logging import add_trace_context

ISSUER = 'Bank of Anthos'
MFA_TOKEN_SECONDS = 300
MFA_MAX_ATTEMPTS = 5
MFA_LOCKOUT_SECONDS = 300

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

    class RateLimited(Exception):
        """Too many wrong second-factor codes"""

    def _session_token(user):
        full_name = '{} {}'.format(user['firstname'], user['lastname'])
        exp_time = datetime.utcnow() + timedelta(seconds=app.config['EXPIRY_SECONDS'])
        payload = {
            'user': user['username'],
            'acct': user['accountid'],
            'name': full_name,
            'iat': datetime.utcnow(),
            'exp': exp_time,
        }
        app.logger.debug('Creating jwt token.')
        return jwt.encode(payload, app.config['PRIVATE_KEY'], algorithm='RS256')

    def _key(purpose):
        material = app.config['PRIVATE_KEY']
        if isinstance(material, str):
            material = material.encode('utf-8')
        return totp.derive_key(material, purpose)

    def _issue_mfa_token(username):
        """Short-lived proof that the password was accepted. It is signed with
        a symmetric key and a different claim set, so it can never be taken
        for a session token (RS256)."""
        payload = {
            'purpose': 'mfa',
            'user': username,
            'exp': datetime.utcnow() + timedelta(seconds=MFA_TOKEN_SECONDS),
        }
        return jwt.encode(payload, _key('mfa-token'), algorithm='HS256')

    def _check_mfa_token(mfa_token, username):
        try:
            claims = jwt.decode(mfa_token, _key('mfa-token'), algorithms=['HS256'])
        except jwt.InvalidTokenError as err:
            raise PermissionError('invalid login') from err
        if claims.get('purpose') != 'mfa' or claims.get('user') != username:
            raise PermissionError('invalid login')

    def _check_second_factor(username, mfa, code):
        """Accept a TOTP code or an unused recovery code, with rate limiting.

        Updates the stored state. Raises RateLimited, or PermissionError for
        a wrong code. Codes and secrets are never logged.
        """
        now = datetime.utcnow()
        locked_until = mfa.get('locked_until')
        if locked_until is not None and locked_until > now:
            raise RateLimited('too many attempts, try again later')

        code = (code or '').strip()
        secret = totp.decrypt_secret(mfa['secret_enc'], _key('totp-secret-material'))
        step = None
        if secret is not None:
            step = totp.verify_totp(secret, code, last_step=mfa.get('last_step'))
        if step is not None:
            users_db.save_mfa(username, {
                'last_step': step, 'failed_attempts': 0, 'locked_until': None})
            return
        recovery = list(mfa.get('recovery_hashes') or [])
        digest = totp.hash_recovery_code(code, _key('recovery-code'))
        if digest in recovery:
            recovery.remove(digest)
            users_db.save_mfa(username, {
                'recovery_hashes': recovery, 'failed_attempts': 0, 'locked_until': None})
            return

        _record_failure(username, mfa)
        raise PermissionError('invalid code')

    @app.route('/login', methods=['GET'])
    def login():
        """Login a user and return a JWT token

        Fails if username doesn't exist or password doesn't match hash

        token expiry time determined by environment variable

        If the user turned on two-factor sign-in, a correct password only
        returns 401 {"mfa_required": true, "mfa_token": ...}. The JWT is
        issued once the request is repeated with that mfa_token and a
        6-digit (or recovery) code instead of the password.

        request fields:
        - username
        - password
        - mfa_token, code (second step only)
        """
        app.logger.debug('Sanitizing login input.')
        username = bleach.clean(request.args.get('username'))
        mfa_token = request.args.get('mfa_token')

        # Get user data
        try:
            app.logger.debug('Getting the user data.')
            user = users_db.get_user(username)
            if user is None:
                raise LookupError('user {} does not exist'.format(username))

            if mfa_token is not None:
                _check_mfa_token(mfa_token, username)
                mfa = users_db.get_mfa(username)
                if not (isinstance(mfa, dict) and mfa.get('enabled')):
                    raise PermissionError('invalid login')
                _check_second_factor(username, mfa, request.args.get('code'))
            else:
                password = bleach.clean(request.args.get('password'))
                # Validate the password
                app.logger.debug('Validating the password.')
                if not bcrypt.checkpw(password.encode('utf-8'), user['passhash']):
                    raise PermissionError('invalid login')
                mfa = users_db.get_mfa(username)
                if isinstance(mfa, dict) and mfa.get('enabled'):
                    return jsonify({'mfa_required': True,
                                    'mfa_token': _issue_mfa_token(username)}), 401

            token = _session_token(user)
            app.logger.info('Login Successful.')
            return jsonify({'token': token}), 200

        except LookupError as err:
            app.logger.error('Error logging in: %s', str(err))
            return str(err), 404
        except RateLimited as err:
            app.logger.error('Error logging in: %s', str(err))
            return str(err), 429
        except PermissionError as err:
            app.logger.error('Error logging in: %s', str(err))
            return str(err), 401
        except SQLAlchemyError as err:
            app.logger.error('Error logging in: %s', str(err))
            return 'failed to retrieve user information', 500

    def _authenticated_user():
        """The username in the request's bearer JWT, or None"""
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return None
        try:
            claims = jwt.decode(header[len('Bearer '):], app.config['PUBLIC_KEY'],
                                algorithms=['RS256'])
        except jwt.InvalidTokenError:
            return None
        return claims.get('user')

    @app.route('/2fa', methods=['GET'])
    def mfa_status():
        """Whether two-factor sign-in is on for the signed-in user.

        Return: {"enabled": bool, "recovery_codes_left": int}
        """
        username = _authenticated_user()
        if username is None:
            return 'unauthorized', 401
        try:
            mfa = users_db.get_mfa(username)
        except SQLAlchemyError as err:
            app.logger.error('Error reading 2FA state: %s', str(err))
            return 'failed to retrieve 2FA state', 500
        enabled = bool(isinstance(mfa, dict) and mfa.get('enabled'))
        left = len(mfa.get('recovery_hashes') or []) if enabled else 0
        return jsonify({'enabled': enabled, 'recovery_codes_left': left}), 200

    @app.route('/2fa/setup', methods=['POST'])
    def mfa_setup():
        """Start setting up 2FA: create a secret that is not active until
        confirmed with /2fa/enable.

        Return: {"secret": ..., "uri": otpauth:// URI}
        """
        username = _authenticated_user()
        if username is None:
            return 'unauthorized', 401
        try:
            mfa = users_db.get_mfa(username)
            if isinstance(mfa, dict) and mfa.get('enabled'):
                return '2FA is already enabled', 409
            secret = totp.new_secret()
            users_db.save_mfa(username, {
                'secret_enc': totp.encrypt_secret(secret, _key('totp-secret-material')),
                'enabled': False,
                'recovery_hashes': [],
                'last_step': None,
                'failed_attempts': 0,
                'locked_until': None,
            })
        except SQLAlchemyError as err:
            app.logger.error('Error setting up 2FA: %s', str(err))
            return 'failed to set up 2FA', 500
        app.logger.info('Started 2FA setup.')
        return jsonify({
            'secret': secret,
            'uri': totp.provisioning_uri(secret, username, ISSUER),
        }), 200

    @app.route('/2fa/enable', methods=['POST'])
    def mfa_enable():
        """Turn 2FA on by confirming a code from the authenticator app.

        request fields:
        - code

        Return: {"recovery_codes": [...]} - shown only this once
        """
        username = _authenticated_user()
        if username is None:
            return 'unauthorized', 401
        try:
            mfa = users_db.get_mfa(username)
            if not isinstance(mfa, dict) or mfa.get('enabled'):
                return 'no 2FA setup in progress', 409
            locked_until = mfa.get('locked_until')
            if locked_until is not None and locked_until > datetime.utcnow():
                return 'too many attempts, try again later', 429
            secret = totp.decrypt_secret(mfa['secret_enc'], _key('totp-secret-material'))
            step = totp.verify_totp(secret, (request.form.get('code') or '').strip()) \
                if secret else None
            if step is None:
                _record_failure(username, mfa)
                return 'invalid code', 401
            codes = totp.new_recovery_codes()
            users_db.save_mfa(username, {
                'enabled': True,
                'last_step': step,
                'failed_attempts': 0,
                'locked_until': None,
                'recovery_hashes': [totp.hash_recovery_code(c, _key('recovery-code'))
                                    for c in codes],
            })
        except SQLAlchemyError as err:
            app.logger.error('Error enabling 2FA: %s', str(err))
            return 'failed to enable 2FA', 500
        app.logger.info('Enabled 2FA.')
        return jsonify({'recovery_codes': codes}), 200

    def _record_failure(username, mfa):
        failed = (mfa.get('failed_attempts') or 0) + 1
        values = {'failed_attempts': failed}
        if failed >= MFA_MAX_ATTEMPTS:
            values = {'failed_attempts': 0,
                      'locked_until': datetime.utcnow() + timedelta(seconds=MFA_LOCKOUT_SECONDS)}
        users_db.save_mfa(username, values)

    @app.route('/2fa/disable', methods=['POST'])
    def mfa_disable():
        """Turn 2FA off after confirming a TOTP or recovery code.

        request fields:
        - code
        """
        username = _authenticated_user()
        if username is None:
            return 'unauthorized', 401
        try:
            mfa = users_db.get_mfa(username)
            if not (isinstance(mfa, dict) and mfa.get('enabled')):
                return '2FA is not enabled', 409
            _check_second_factor(username, mfa, request.form.get('code'))
            users_db.delete_mfa(username)
        except RateLimited as err:
            return str(err), 429
        except PermissionError as err:
            return str(err), 401
        except SQLAlchemyError as err:
            app.logger.error('Error disabling 2FA: %s', str(err))
            return 'failed to disable 2FA', 500
        app.logger.info('Disabled 2FA.')
        return jsonify({}), 200

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
    try:
        users_db.create_mfa_table()
    except SQLAlchemyError:
        app.logger.warning("could not ensure the 2FA table exists")
    return app


if __name__ == "__main__":
    # Create an instance of flask server when called directly
    USERSERVICE = create_app()
    USERSERVICE.run()
