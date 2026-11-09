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

"""Web service for frontend
"""

# Module imports
import concurrent.futures
import html
import json
import logging
import os
import socket
from decimal import Decimal
from pathlib import Path
from time import sleep
from urllib.parse import urlencode

import requests
from requests.exceptions import HTTPError, RequestException
import jwt
from flask import Flask, abort, jsonify, make_response, redirect, request, url_for

from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.propagate import set_global_textmap
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.jinja2 import Jinja2Instrumentor

# Local imports
from api_call import ApiCall, ApiRequest
from traced_thread_pool_executor import TracedThreadPoolExecutor
from trace_logging import add_trace_context

# Local constants
BALANCE_NAME = "balance"
CONTACTS_NAME = "contacts"
TRANSACTION_LIST_NAME = "transaction_list"


class TransactionError(UserWarning):
    """The ledger could not process a transaction; carries the status to respond with"""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


# The React single-page app, built into static/dist by `npm run build` in web/
SHELL_PATH = Path(__file__).resolve().parent / 'static' / 'dist' / 'index.html'
# Where the shell puts the message that a form post wants the app to show
FLASH_MARKER = '<!--boa-flash-->'
# Served when the app has not been built (the unit tests, for one)
SHELL_FALLBACK = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    '<title>Bank of Anthos</title></head>'
    f'<body><div id="root">{FLASH_MARKER}</div></body></html>')


def flash_markup(flash):
    """
    HTML for the message a form post wants the single-page app to show.

    It carries the message as JSON for the app, which reads it when it starts,
    and as an alert for what is on screen until the app has replaced it.
    """
    if not flash:
        return ''
    is_error = bool(flash.get('isError'))
    data = json.dumps({'message': flash['message'], 'isError': is_error})
    role = ' role="alert"' if is_error else ''
    css_class = 'alert-message-container' + (' text-danger' if is_error else '')
    return (
        # "<" is escaped so that the message cannot close the script element
        f'<script id="boa-flash" type="application/json">{data.replace("<", "\\u003c")}</script>'
        f'<div class="container"><div id="alert-message-div"{role}>'
        f'<h5 id="alert-message" class="{css_class}">{html.escape(flash["message"])}</h5>'
        '</div></div>')


def render_shell(flash=None):
    """The single-page app's HTML, with the message to show when it starts"""
    try:
        page = SHELL_PATH.read_text(encoding='utf-8')
    except OSError:
        page = SHELL_FALLBACK
    return page.replace(FLASH_MARKER, flash_markup(flash))


# pylint: disable-msg=too-many-locals
# pylint: disable-msg=too-many-branches
def create_app():
    """Flask application factory to create instances
    of the Frontend Flask App
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
        return os.environ.get('VERSION'), 200

    @app.route('/ready', methods=['GET'])
    def readiness():
        """
        Readiness probe
        """
        return 'ok', 200

    @app.route('/whereami', methods=['GET'])
    def whereami():
        """
        Returns the cluster name + zone name where this Pod is running.

        """
        return "Cluster: " + cluster_name + ", Pod: " + pod_name + ", Zone: " + pod_zone, 200

    @app.route("/")
    def root():
        """
        Serves the single-page app: the home view or the login view,
        depending on authentication status.
        """
        token = request.cookies.get(app.config['TOKEN_NAME'])
        if not verify_token(token):
            return login_page()
        return home()

    @app.route("/home")
    def home():
        """
        Serves the single-page app. Redirects to /login if token is not valid
        """
        token = request.cookies.get(app.config['TOKEN_NAME'])
        if not verify_token(token):
            # user isn't authenticated
            app.logger.debug('User isn\'t authenticated. Redirecting to login page.')
            return redirect(url_for('login_page',
                                    _external=True,
                                    _scheme=app.config['SCHEME']))
        return _render_shell()

    def _render_shell(flash=None, status=200):
        """
        Responds with the React single-page app.

        Params: flash - optional {'message', 'isError'} dict that the app shows
                        in its alert banner when it starts
                status - HTTP status code of the response
        """
        resp = make_response(render_shell(flash), status)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    def _failure_message(kind, reason=None):
        return f'{kind} failed: {reason}' if reason else f'{kind} failed'

    def _transaction_failed(kind, reason=None, status=400):
        """
        Responds with the single-page app showing an error message
        and a failure status.

        Params: kind - 'Payment' or 'Deposit'
                reason - optional explanation shown after the message
                status - HTTP status code of the response
        """
        return _render_shell(flash={'message': _failure_message(kind, reason),
                                    'isError': True},
                             status=status)

    def _load_home(token):
        """
        Fetches what the home view shows from the backend services.

        A part that could not be loaded is None (balance, history) or empty
        (contacts).

        Params: token - the user's valid JWT
        """
        token_data = decode_token(token)
        username = token_data['user']
        account_id = token_data['acct']

        hed = {'Authorization': 'Bearer ' + token}

        api_calls = [
            # get balance
            ApiCall(display_name=BALANCE_NAME,
                    api_request=ApiRequest(url=f'{app.config["BALANCES_URI"]}/{account_id}',
                                           headers=hed,
                                           timeout=app.config['BACKEND_TIMEOUT']),
                    logger=app.logger),
            # get history
            ApiCall(display_name=TRANSACTION_LIST_NAME,
                    api_request=ApiRequest(url=f'{app.config["HISTORY_URI"]}/{account_id}',
                                           headers=hed,
                                           timeout=app.config['BACKEND_TIMEOUT']),
                    logger=app.logger),
            # get contacts
            ApiCall(display_name=CONTACTS_NAME,
                    api_request=ApiRequest(url=f'{app.config["CONTACTS_URI"]}/{username}',
                                           headers=hed,
                                           timeout=app.config['BACKEND_TIMEOUT']),
                    logger=app.logger)
        ]

        api_response = {BALANCE_NAME: None,
                        TRANSACTION_LIST_NAME: None,
                        CONTACTS_NAME: []}

        tracer = trace.get_tracer(__name__)
        with TracedThreadPoolExecutor(tracer, max_workers=3) as executor:
            future_to_api_call = {
                executor.submit(api_call.make_call):
                    api_call for api_call in api_calls
            }

            for future in concurrent.futures.as_completed(future_to_api_call):
                if future.result():
                    api_call = future_to_api_call[future]
                    api_response[api_call.display_name] = future.result().json()

        _populate_contact_labels(account_id,
                                 api_response[TRANSACTION_LIST_NAME],
                                 api_response[CONTACTS_NAME])

        return {'account_id': account_id,
                'name': token_data['name'],
                'balance': api_response[BALANCE_NAME],
                'history': api_response[TRANSACTION_LIST_NAME],
                'contacts': api_response[CONTACTS_NAME]}

    def _populate_contact_labels(account_id, transactions, contacts):
        """
        Populate contact labels for the passed transactions.

        Side effect:
            Take each transaction and set the 'accountLabel' field with the label of
            the contact each transaction was associated with. If there was no
            associated contact, set 'accountLabel' to None.
            If any parameter is None, nothing happens.

        Params: account_id - the account id for the user owning the transaction list
                transactions - a list of transactions as key/value dicts
                            [{transaction1}, {transaction2}, ...]
                contacts - a list of contacts as key/value dicts
                        [{contact1}, {contact2}, ...]
        """
        app.logger.debug('Populating contact labels.')
        if account_id is None or transactions is None or contacts is None:
            return

        # Map contact accounts to their labels. If no label found, default to None.
        contact_map = {c['account_num']: c.get('label') for c in contacts}

        # Populate the 'accountLabel' field. If no match found, default to None.
        for trans in transactions:
            if trans['toAccountNum'] == account_id:
                trans['accountLabel'] = contact_map.get(trans['fromAccountNum'])
            elif trans['fromAccountNum'] == account_id:
                trans['accountLabel'] = contact_map.get(trans['toAccountNum'])

    # JSON API used by the single-page app

    def _json_body():
        """The JSON object sent by the client; empty if it sent anything else"""
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    def _valid_token():
        """The request's token if it is valid, otherwise None"""
        token = request.cookies.get(app.config['TOKEN_NAME'])
        return token if verify_token(token) else None

    def _unauthorized():
        return jsonify(error='Not authenticated'), 401

    @app.route('/api/config', methods=['GET'])
    def api_config():
        """
        What the single-page app needs to know about the deployment
        """
        return jsonify(bank_name=os.getenv('BANK_NAME', 'Bank of Anthos'),
                       cymbal_logo=os.getenv('CYMBAL_LOGO', 'false') == 'true',
                       cluster_name=cluster_name,
                       pod_name=pod_name,
                       pod_zone=pod_zone,
                       platform=platform,
                       platform_display_name=platform_display_name,
                       default_username=os.getenv('DEFAULT_USERNAME', ''),
                       default_password=os.getenv('DEFAULT_PASSWORD', ''))

    @app.route('/api/session', methods=['GET'])
    def api_session():
        """
        Who is signed in. Responds 401 if token is not valid
        """
        token = _valid_token()
        if token is None:
            return _unauthorized()
        token_data = decode_token(token)
        return jsonify(name=token_data['name'],
                       username=token_data['user'],
                       account_id=token_data['acct'])

    @app.route('/api/home', methods=['GET'])
    def api_home():
        """
        Balance, transaction history and contacts of the signed in user.
        Responds 401 if token is not valid
        """
        token = _valid_token()
        if token is None:
            return _unauthorized()
        return jsonify(_load_home(token))

    def _make_payment(data):
        """
        Submits a payment of the signed in user to the ledgerwriter service.

        Params: data - the payment form fields (account_num, amount, uuid and,
                       for a new recipient, contact_account_num and contact_label)
        """
        account_id = decode_token(request.cookies.get(app.config['TOKEN_NAME']))['acct']
        recipient = data['account_num']
        if recipient == 'add':
            recipient = data['contact_account_num']
            label = data.get('contact_label', None)
            if label:
                # new contact. Add to contacts list
                _add_contact(label,
                             recipient,
                             app.config['LOCAL_ROUTING'],
                             False)

        payment_amount = int(Decimal(str(data['amount'])) * 100)
        transaction_data = {"fromAccountNum": account_id,
                            "fromRoutingNum": app.config['LOCAL_ROUTING'],
                            "toAccountNum": recipient,
                            "toRoutingNum": app.config['LOCAL_ROUTING'],
                            "amount": payment_amount,
                            "uuid": data['uuid']}
        _submit_transaction(transaction_data)

    def _make_deposit(data):
        """
        Submits a deposit into the signed in user's account to the
        ledgerwriter service.

        Params: data - the deposit form fields (account, amount, uuid and, for
                       a new external account, external_account_num,
                       external_routing_num and external_label)
        Raise: UserWarning if the routing number is the local routing number
        """
        account_id = decode_token(request.cookies.get(app.config['TOKEN_NAME']))['acct']
        if data['account'] == 'add':
            external_account_num = data['external_account_num']
            external_routing_num = data['external_routing_num']
            if external_routing_num == app.config['LOCAL_ROUTING']:
                raise UserWarning("invalid routing number")
            external_label = data.get('external_label', None)
            if external_label:
                # new contact. Add to contacts list
                _add_contact(external_label,
                             external_account_num,
                             external_routing_num,
                             True)
        else:
            account_details = data['account']
            if isinstance(account_details, str):
                account_details = json.loads(account_details)
            external_account_num = account_details['account_num']
            external_routing_num = account_details['routing_num']

        transaction_data = {"fromAccountNum": external_account_num,
                            "fromRoutingNum": external_routing_num,
                            "toAccountNum": account_id,
                            "toRoutingNum": app.config['LOCAL_ROUTING'],
                            "amount": int(Decimal(str(data['amount'])) * 100),
                            "uuid": data['uuid']}
        _submit_transaction(transaction_data)

    def _perform_transaction(kind, make, data):
        """
        Runs make(data) and reports how it went.

        Params: kind - 'Payment' or 'Deposit'
                make - _make_payment or _make_deposit
                data - the submitted fields
        Returns: (None, 200) on success, otherwise (reason, status) where
                 reason completes "<kind> failed" and may be None
        """
        action = kind.lower()
        try:
            make(data)
            app.logger.info('%s submitted successfully.', kind)
            return None, 200
        except requests.exceptions.RequestException as err:
            app.logger.error('Error submitting %s: %s', action, str(err))
            return None, 502
        except TransactionError as err:
            app.logger.error('Error submitting %s: %s', action, str(err))
            return str(err), err.status_code
        except UserWarning as warn:
            app.logger.error('Error submitting %s: %s', action, str(warn))
            return str(warn), 400
        except (KeyError, ValueError, ArithmeticError) as input_err:
            app.logger.error('Error submitting %s: %s', action, str(input_err))
            if isinstance(input_err, KeyError):
                return 'missing form field', 400
            return f'{data.get("amount", "")} is not a valid number', 400

    @app.route('/payment', methods=['POST'])
    def payment():
        """
        Submits payment request to ledgerwriter service (HTML form post)

        Fails if:
        - token is not valid
        - basic validation checks fail
        - response code from ledgerwriter is not 201
        """
        token = request.cookies.get(app.config['TOKEN_NAME'])
        if not verify_token(token):
            # user isn't authenticated
            app.logger.error('Error submitting payment: user is not authenticated.')
            return abort(401)
        reason, status = _perform_transaction('Payment', _make_payment, request.form)
        if status != 200:
            return _transaction_failed('Payment', reason, status)
        return redirect(code=303,
                        location=url_for('home',
                                         msg='Payment successful',
                                         _external=True,
                                         _scheme=app.config['SCHEME']))

    @app.route('/deposit', methods=['POST'])
    def deposit():
        """
        Submits deposit request to ledgerwriter service (HTML form post)

        Fails if:
        - token is not valid
        - routing number == local routing number
        - response code from ledgerwriter is not 201
        """
        token = request.cookies.get(app.config['TOKEN_NAME'])
        if not verify_token(token):
            # user isn't authenticated
            app.logger.error('Error submitting deposit: user is not authenticated.')
            return abort(401)
        reason, status = _perform_transaction('Deposit', _make_deposit, request.form)
        if status != 200:
            return _transaction_failed('Deposit', reason, status)
        return redirect(code=303,
                        location=url_for('home',
                                         msg='Deposit successful',
                                         _external=True,
                                         _scheme=app.config['SCHEME']))

    def _api_transaction(kind, make):
        """Runs a transaction submitted by the single-page app as JSON"""
        if _valid_token() is None:
            app.logger.error('Error submitting %s: user is not authenticated.', kind.lower())
            return _unauthorized()
        reason, status = _perform_transaction(kind, make, _json_body())
        if status != 200:
            return jsonify(error=_failure_message(kind, reason)), status
        return jsonify(message=f'{kind} successful')

    @app.route('/api/payment', methods=['POST'])
    def api_payment():
        """
        Submits payment request to ledgerwriter service (JSON)
        """
        return _api_transaction('Payment', _make_payment)

    @app.route('/api/deposit', methods=['POST'])
    def api_deposit():
        """
        Submits deposit request to ledgerwriter service (JSON)
        """
        return _api_transaction('Deposit', _make_deposit)

    def _submit_transaction(transaction_data):
        app.logger.debug('Submitting transaction.')
        token = request.cookies.get(app.config['TOKEN_NAME'])
        hed = {'Authorization': 'Bearer ' + token,
               'content-type': 'application/json'}
        resp = requests.post(url=app.config["TRANSACTIONS_URI"],
                             data=jsonify(transaction_data).data,
                             headers=hed,
                             timeout=app.config['BACKEND_TIMEOUT'])
        try:
            resp.raise_for_status()  # Raise on HTTP Status code 4XX or 5XX
        except requests.exceptions.HTTPError as http_request_err:
            # 4XX: the ledger rejected the transaction; 5XX: backend failure
            status = 400 if resp.status_code < 500 else 502
            raise TransactionError(resp.text, status) from http_request_err
        # Short delay to allow the transaction to propagate to balancereader
        # and transaction-history
        sleep(0.25)

    def _add_contact(label, acct_num, routing_num, is_external_acct=False):
        """
        Submits a new contact to the contact service.

        Raise: UserWarning  if the response status is 4xx or 5xx.
        """
        app.logger.debug('Adding new contact.')
        token = request.cookies.get(app.config['TOKEN_NAME'])
        hed = {'Authorization': 'Bearer ' + token,
               'content-type': 'application/json'}
        contact_data = {
            'label': label,
            'account_num': acct_num,
            'routing_num': routing_num,
            'is_external': is_external_acct
        }
        token_data = decode_token(token)
        url = '{}/{}'.format(app.config["CONTACTS_URI"], token_data['user'])
        resp = requests.post(url=url,
                             data=jsonify(contact_data).data,
                             headers=hed,
                             timeout=app.config['BACKEND_TIMEOUT'])
        try:
            resp.raise_for_status()  # Raise on HTTP Status code 4XX or 5XX
        except requests.exceptions.HTTPError as http_request_err:
            raise UserWarning(resp.text) from http_request_err

    @app.route("/login", methods=['GET'])
    def login_page():
        """
        Serves the single-page app. Redirects to /home if user already has a valid token.
        If this is an oauth flow, then redirect to a consent form.
        """
        token = request.cookies.get(app.config['TOKEN_NAME'])
        response_type = request.args.get('response_type')
        client_id = request.args.get('client_id')
        app_name = request.args.get('app_name')
        redirect_uri = request.args.get('redirect_uri')
        state = request.args.get('state')
        if ('REGISTERED_OAUTH_CLIENT_ID' in os.environ and
            'ALLOWED_OAUTH_REDIRECT_URI' in os.environ and
                response_type == 'code'):
            app.logger.debug('Login with response_type=code')
            if client_id != os.environ['REGISTERED_OAUTH_CLIENT_ID']:
                return redirect(url_for('login',
                                        msg='Error: Invalid client_id',
                                        _external=True,
                                        _scheme=app.config['SCHEME']))
            if redirect_uri != os.environ['ALLOWED_OAUTH_REDIRECT_URI']:
                return redirect(url_for('login',
                                        msg='Error: Invalid redirect_uri',
                                        _external=True,
                                        _scheme=app.config['SCHEME']))
            if verify_token(token):
                app.logger.debug('User already authenticated. Redirecting to /consent')
                return make_response(redirect(url_for('consent',
                                                      state=state,
                                                      redirect_uri=redirect_uri,
                                                      app_name=app_name,
                                                      _external=True,
                                                      _scheme=app.config['SCHEME'])))
        else:
            if verify_token(token):
                # already authenticated
                app.logger.debug('User already authenticated. Redirecting to /home')
                return redirect(url_for('home',
                                        _external=True,
                                        _scheme=app.config['SCHEME']))

        return _render_shell()

    def _authenticate(username, password):
        """
        Asks userservice for a token.

        Returns: (token, max_age of the token in seconds)
        Raise: RequestException/HTTPError if userservice does not accept the
               credentials
        """
        app.logger.debug('Logging in.')
        req = requests.get(url=app.config["LOGIN_URI"],
                           params={'username': username, 'password': password},
                           timeout=app.config['BACKEND_TIMEOUT']*2)
        req.raise_for_status()  # Raise on HTTP Status code 4XX or 5XX
        token = req.json()['token']
        claims = decode_token(token)
        return token, claims['exp'] - claims['iat']

    def _consent_args(args):
        """
        The oauth parameters of a login that must continue on the consent
        form, or None if the login is not part of an oauth flow
        """
        if ('response_type' in args and
                'state' in args and
                'redirect_uri' in args and
                args['response_type'] == 'code'):
            return {'state': args['state'],
                    'redirect_uri': args['redirect_uri'],
                    'app_name': args.get('app_name')}
        return None

    @app.route('/login', methods=['POST'])
    def login():
        """
        Submits login request to userservice and saves resulting token
        (HTML form post)

        Fails if userservice does not accept input username and password
        """
        return _login_helper(request.form['username'],
                             request.form['password'],
                             request.args)

    def _login_helper(username, password, request_args):
        try:
            token, max_age = _authenticate(username, password)

            consent_args = _consent_args(request_args)
            if consent_args is not None:
                resp = make_response(redirect(url_for('consent',
                                                      _external=True,
                                                      _scheme=app.config['SCHEME'],
                                                      **consent_args)))
            else:
                resp = make_response(redirect(url_for('home',
                                                      _external=True,
                                                      _scheme=app.config['SCHEME'])))
            resp.set_cookie(app.config['TOKEN_NAME'], token, max_age=max_age)
            app.logger.info('Successfully logged in.')
            return resp
        except (RequestException, HTTPError) as err:
            app.logger.error('Error logging in: %s', str(err))
        return redirect(url_for('login',
                                msg='Login Failed',
                                _external=True,
                                _scheme=app.config['SCHEME']))

    def _api_login_helper(username, password, body):
        """
        Logs in for the single-page app: sets the token cookie and tells
        the app where to go next. Returns None if the login failed.
        """
        try:
            token, max_age = _authenticate(username, password)
        except (RequestException, HTTPError, KeyError, ValueError) as err:
            app.logger.error('Error logging in: %s', str(err))
            return None
        consent_args = _consent_args(body)
        if consent_args is not None:
            location = '/consent?' + urlencode(
                {k: v for k, v in consent_args.items() if v is not None})
        else:
            location = '/home'
        resp = jsonify(redirect=location)
        resp.set_cookie(app.config['TOKEN_NAME'], token, max_age=max_age)
        app.logger.info('Successfully logged in.')
        return resp

    @app.route('/api/login', methods=['POST'])
    def api_login():
        """
        Submits login request to userservice and saves resulting token (JSON)

        Responds 401 if userservice does not accept input username and password
        """
        body = _json_body()
        resp = _api_login_helper(str(body.get('username', '')),
                                 str(body.get('password', '')),
                                 body)
        if resp is None:
            return jsonify(error='Login failed'), 401
        return resp

    @app.route("/consent", methods=['GET'])
    def consent_page():
        """Serves the single-page app, which renders the consent page.

        Retrieves auth code if the user has
        already logged in and consented.
        """
        redirect_uri = request.args.get('redirect_uri')
        state = request.args.get('state')
        app_name = request.args.get('app_name')
        token = request.cookies.get(app.config['TOKEN_NAME'])
        consented = request.cookies.get(app.config['CONSENT_COOKIE'])
        if verify_token(token):
            if consented == "true":
                app.logger.debug('User consent already granted.')
                resp = _auth_callback_helper(state, redirect_uri, token)
                return resp

            return _render_shell()

        return make_response(redirect(url_for('login',
                                              response_type="code",
                                              state=state,
                                              redirect_uri=redirect_uri,
                                              app_name=app_name,
                                              _external=True,
                                              _scheme=app.config['SCHEME'])))

    @app.route('/consent', methods=['POST'])
    def consent():
        """
        Check consent, write cookie if yes, and redirect accordingly
        (HTML form post)
        """
        consent = request.args['consent']
        state = request.args['state']
        redirect_uri = request.args['redirect_uri']
        token = request.cookies.get(app.config['TOKEN_NAME'])

        app.logger.debug('Checking consent. consent: %s', consent)

        if consent == "true":
            app.logger.info('User consent granted.')
            resp = _auth_callback_helper(state, redirect_uri, token)
            resp.set_cookie(app.config['CONSENT_COOKIE'], 'true')
        else:
            app.logger.info('User consent denied.')
            resp = make_response(redirect(redirect_uri + '#error=access_denied', 302))
        return resp

    @app.route('/api/consent', methods=['POST'])
    def api_consent():
        """
        Check consent, write cookie if yes, and tell the single-page app
        where to send the browser (JSON)

        Fails if the redirect URI is not the one registered for the oauth client
        """
        if _valid_token() is None:
            return _unauthorized()
        body = _json_body()
        redirect_uri = body.get('redirect_uri')
        if ('REGISTERED_OAUTH_CLIENT_ID' not in os.environ or
                redirect_uri != os.environ.get('ALLOWED_OAUTH_REDIRECT_URI')):
            return jsonify(error='Invalid redirect_uri'), 400
        token = request.cookies.get(app.config['TOKEN_NAME'])
        if body.get('consent') is True:
            app.logger.info('User consent granted.')
            resp = jsonify(redirect=_auth_callback_location(
                str(body.get('state', '')), redirect_uri, token))
            resp.set_cookie(app.config['CONSENT_COOKIE'], 'true')
        else:
            app.logger.info('User consent denied.')
            resp = jsonify(redirect=redirect_uri + '#error=access_denied')
        return resp

    def _auth_callback_location(state, redirect_uri, token):
        """
        Retrieves the authorization code from the oauth client

        Returns: where to send the browser next: the client's location, or
                 the redirect URI with an error
        """
        try:
            app.logger.debug('Retrieving authorization code.')
            callback_response = requests.post(url=redirect_uri,
                                              data={'state': state, 'id_token': token},
                                              timeout=app.config['BACKEND_TIMEOUT'],
                                              allow_redirects=False)
            if callback_response.status_code == requests.codes.found:
                app.logger.info('Successfully retrieved auth code.')
                return callback_response.headers['Location']

            app.logger.error('Unexpected response status: %s', callback_response.status_code)
        except requests.exceptions.RequestException as err:
            app.logger.error('Error retrieving auth code: %s', str(err))
        return redirect_uri + '#error=server_error'

    def _auth_callback_helper(state, redirect_uri, token):
        return make_response(redirect(
            _auth_callback_location(state, redirect_uri, token), 302))

    @app.route("/signup", methods=['GET'])
    def signup_page():
        """
        Serves the single-page app. Redirects to /home if token is valid
        """
        token = request.cookies.get(app.config['TOKEN_NAME'])
        if verify_token(token):
            # already authenticated
            app.logger.debug('User already authenticated. Redirecting to /home')
            return redirect(url_for('home',
                                    _external=True,
                                    _scheme=app.config['SCHEME']))
        return _render_shell()

    @app.route("/signup", methods=['POST'])
    def signup():
        """
        Submits signup request to userservice (HTML form post)

        Fails if userservice does not accept input form data
        """
        try:
            # create user
            app.logger.debug('Creating new user.')
            resp = requests.post(url=app.config["USERSERVICE_URI"],
                                 data=request.form,
                                 timeout=app.config['BACKEND_TIMEOUT'])
            if resp.status_code == 201:
                # user created. Attempt login
                app.logger.info('New user created.')
                return _login_helper(request.form['username'],
                                     request.form['password'],
                                     request.args)
        except requests.exceptions.RequestException as err:
            app.logger.error('Error creating new user: %s', str(err))
        return redirect(url_for('login',
                                msg='Error: Account creation failed',
                                _external=True,
                                _scheme=app.config['SCHEME']))

    @app.route('/api/signup', methods=['POST'])
    def api_signup():
        """
        Submits signup request to userservice and logs the new user in (JSON)

        Responds 400 if userservice does not accept the input
        """
        body = _json_body()
        try:
            app.logger.debug('Creating new user.')
            resp = requests.post(url=app.config["USERSERVICE_URI"],
                                 data={k: str(v) for k, v in body.items()},
                                 timeout=app.config['BACKEND_TIMEOUT'])
            if resp.status_code == 201:
                # user created. Attempt login
                app.logger.info('New user created.')
                login_resp = _api_login_helper(str(body.get('username', '')),
                                               str(body.get('password', '')),
                                               body)
                # the account exists even if the login failed: go sign in
                return login_resp or jsonify(redirect='/login')
        except requests.exceptions.RequestException as err:
            app.logger.error('Error creating new user: %s', str(err))
        return jsonify(error='Account creation failed'), 400

    @app.route('/logout', methods=['POST'])
    def logout():
        """
        Logs out user by deleting token cookie and redirecting to login page
        """
        app.logger.info('Logging out.')
        resp = make_response(redirect(url_for('login_page',
                                              _external=True,
                                              _scheme=app.config['SCHEME'])))
        resp.delete_cookie(app.config['TOKEN_NAME'])
        resp.delete_cookie(app.config['CONSENT_COOKIE'])
        return resp

    @app.route('/api/logout', methods=['POST'])
    def api_logout():
        """
        Logs out user by deleting token cookie (JSON)
        """
        app.logger.info('Logging out.')
        resp = jsonify(redirect='/login')
        resp.delete_cookie(app.config['TOKEN_NAME'])
        resp.delete_cookie(app.config['CONSENT_COOKIE'])
        return resp

    def decode_token(token):
        return jwt.decode(algorithms='RS256',
                          jwt=token,
                          options={"verify_signature": False})

    def verify_token(token):
        """
        Validates token using userservice public key
        """
        app.logger.debug('Verifying token.')
        if token is None:
            return False
        try:
            jwt.decode(algorithms='RS256',
                       jwt=token,
                       key=app.config['PUBLIC_KEY'],
                       options={"verify_signature": True})
            app.logger.debug('Token verified.')
            return True
        except jwt.exceptions.InvalidTokenError as err:
            app.logger.error('Error validating token: %s', str(err))
            return False

    # set up global variables
    app.config["TRANSACTIONS_URI"] = 'http://{}/transactions'.format(
        os.environ.get('TRANSACTIONS_API_ADDR'))
    app.config["USERSERVICE_URI"] = 'http://{}/users'.format(
        os.environ.get('USERSERVICE_API_ADDR'))
    app.config["BALANCES_URI"] = 'http://{}/balances'.format(
        os.environ.get('BALANCES_API_ADDR'))
    app.config["HISTORY_URI"] = 'http://{}/transactions'.format(
        os.environ.get('HISTORY_API_ADDR'))
    app.config["LOGIN_URI"] = 'http://{}/login'.format(
        os.environ.get('USERSERVICE_API_ADDR'))
    app.config["CONTACTS_URI"] = 'http://{}/contacts'.format(
        os.environ.get('CONTACTS_API_ADDR'))
    app.config['PUBLIC_KEY'] = open(os.environ.get('PUB_KEY_PATH'), 'r').read()
    app.config['LOCAL_ROUTING'] = os.getenv('LOCAL_ROUTING_NUM')
    # timeout in seconds for calls to the backend
    app.config['BACKEND_TIMEOUT'] = int(os.getenv('BACKEND_TIMEOUT', '4'))
    app.config['TOKEN_NAME'] = 'token'
    app.config['CONSENT_COOKIE'] = 'consented'
    app.config['SCHEME'] = os.environ.get('SCHEME', 'http')

    # where am I?
    metadata_server = os.getenv('METADATA_SERVER', 'metadata.google.internal')
    metadata_url = f'http://{metadata_server}/computeMetadata/v1/'
    metadata_headers = {'Metadata-Flavor': 'Google'}

    # get GKE cluster name
    cluster_name = os.getenv('CLUSTER_NAME', 'unknown')
    try:
        req = requests.get(metadata_url + 'instance/attributes/cluster-name',
                           headers=metadata_headers,
                           timeout=app.config['BACKEND_TIMEOUT'])
        if req.ok:
            cluster_name = str(req.text)
    except (RequestException, HTTPError) as err:
        app.logger.warning(
            "Unable to retrieve cluster name from metadata server %s.", metadata_server)

    # get GKE pod name
    pod_name = "unknown"
    pod_name = socket.gethostname()

    # get GKE node zone
    pod_zone = os.getenv('POD_ZONE', 'unknown')
    try:
        req = requests.get(metadata_url + 'instance/zone',
                           headers=metadata_headers,
                           timeout=app.config['BACKEND_TIMEOUT'])
        if req.ok:
            pod_zone = str(req.text.split("/")[3])
    except (RequestException, HTTPError) as err:
        app.logger.warning("Unable to retrieve zone from metadata server %s.", metadata_server)

    # Set up logging
    app.logger.handlers = logging.getLogger('gunicorn.error').handlers
    app.logger.setLevel(logging.getLogger('gunicorn.error').level)
    # Put the trace id and span id on every line, for the app logger and for the
    # database helpers that log through it (they share gunicorn's handlers)
    add_trace_context(logging.getLogger('gunicorn.error'), app.logger)
    app.logger.info('Starting frontend service.')

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
        # Add tracing auto-instrumentation for Flask, jinja and requests
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
        Jinja2Instrumentor().instrument()
    else:
        app.logger.info("🚫 Tracing disabled.")

    platform = os.getenv('ENV_PLATFORM', None)
    platform_display_name = None
    if platform is not None:
        platform = platform.lower()
        if platform not in ['alibaba', 'aws', 'azure', 'gcp', 'local', 'onprem']:
            app.logger.error("Platform '%s' not supported, defaulting to None", platform)
            platform = None
        else:
            app.logger.info("Platform is set to '%s'", platform)
            if platform == 'alibaba':
                platform_display_name = "Alibaba Cloud"
            elif platform == 'aws':
                platform_display_name = "AWS"
            elif platform == 'azure':
                platform_display_name = "Azure"
            elif platform == 'gcp':
                platform_display_name = "Google Cloud"
            elif platform == 'local':
                platform_display_name = "Local"
            elif platform == 'onprem':
                platform_display_name = "On-Premises"
    else:
        app.logger.info("ENV_PLATFORM environment variable is not set")

    return app


if __name__ == "__main__":
    # Create an instance of flask server when called directly
    FRONTEND = create_app()
    FRONTEND.run()
