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

"""Web service for savings goals.

Lets a user create named goals with a target amount, list and delete them,
and move money into them from their checking account.
"""

import atexit
import logging
import os
import sys

import jwt
import requests
from flask import Flask, jsonify, request
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.propagate import set_global_textmap
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from db import GoalsDb
from trace_logging import add_trace_context

MAX_NAME_LENGTH = 40
MAX_GOALS = 20
MAX_AMOUNT_CENTS = 100_000_000_000


def _is_cents(value):
    """True for a positive integer (not a bool)"""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def create_app():
    """Flask application factory for the savings goals service"""
    app = Flask(__name__)

    # pylint: disable=unused-variable
    @app.route("/version", methods=["GET"])
    def version():
        """Service version endpoint"""
        return app.config["VERSION"], 200

    @app.route("/ready", methods=["GET"])
    def ready():
        """Readiness probe."""
        return "ok", 200

    def _authenticate(username):
        """Return (token, claims) or raise PermissionError / InvalidTokenError"""
        auth_header = request.headers.get("Authorization")
        token = auth_header.split(" ")[-1] if auth_header else ""
        claims = jwt.decode(token, key=app.config["PUBLIC_KEY"],
                            algorithms="RS256")
        if username != claims["user"]:
            raise PermissionError
        return token, claims

    def _guard(func):
        """Map authentication and database errors to responses"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (PermissionError, jwt.exceptions.InvalidTokenError) as err:
                app.logger.error("Savings goals auth error: %s", str(err))
                return "authentication denied", 401
            except SQLAlchemyError as err:
                app.logger.error("Savings goals database error: %s", str(err))
                return "database error", 500
        wrapper.__name__ = func.__name__
        return wrapper

    @app.route("/goals/<username>", methods=["GET"])
    @_guard
    def get_goals(username):
        """List the goals of the authenticated user"""
        _authenticate(username)
        return jsonify(goals_db.get_goals(username)), 200

    @app.route("/goals/<username>", methods=["POST"])
    @_guard
    def add_goal(username):
        """Create a goal. Body: {"name": str (<= 40 chars), "target": cents}"""
        _authenticate(username)
        req = request.get_json(silent=True)
        if not isinstance(req, dict) or "name" not in req or "target" not in req:
            return "missing required field(s)", 400
        name = req["name"]
        if not isinstance(name, str) or not name.strip():
            return "goal name is required", 400
        name = name.strip()
        if len(name) > MAX_NAME_LENGTH:
            return f"goal name must be {MAX_NAME_LENGTH} characters or fewer", 400
        target = req["target"]
        if not _is_cents(target) or target > MAX_AMOUNT_CENTS:
            return "target must be a positive amount", 400
        if goals_db.count_goals(username) >= MAX_GOALS:
            return f"you can have at most {MAX_GOALS} goals", 400
        goal = goals_db.add_goal(username, name, target)
        app.logger.info("Created savings goal.")
        return jsonify(goal), 201

    @app.route("/goals/<username>/<int:goal_id>", methods=["DELETE"])
    @_guard
    def delete_goal(username, goal_id):
        """Delete one of the user's goals"""
        _authenticate(username)
        if not goals_db.delete_goal(username, goal_id):
            return "goal not found", 404
        return "", 204

    @app.route("/goals/<username>/<int:goal_id>/contributions", methods=["POST"])
    @_guard
    def contribute(username, goal_id):
        """Move money from the checking account into a goal as a ledger transfer.

        Body: {"amount": cents, "uuid": str}. The amount must be positive and
        no more than the checking balance.
        """
        token, claims = _authenticate(username)
        req = request.get_json(silent=True)
        if not isinstance(req, dict) or "amount" not in req or "uuid" not in req:
            return "missing required field(s)", 400
        amount = req["amount"]
        if not _is_cents(amount) or amount > MAX_AMOUNT_CENTS:
            return "amount must be a positive number", 400
        goal = goals_db.get_goal(username, goal_id)
        if goal is None:
            return "goal not found", 404
        headers = {"Authorization": "Bearer " + token}
        timeout = app.config["BACKEND_TIMEOUT"]
        try:
            balance_resp = requests.get(
                f'{app.config["BALANCES_URI"]}/{claims["acct"]}',
                headers=headers, timeout=timeout)
            balance_resp.raise_for_status()
            balance = int(balance_resp.json())
        except (requests.exceptions.RequestException, ValueError) as err:
            app.logger.error("Could not read balance: %s", str(err))
            return "could not read the checking balance", 502
        if amount > balance:
            return "amount is more than the checking balance", 400
        transaction = {
            "fromAccountNum": claims["acct"],
            "fromRoutingNum": app.config["LOCAL_ROUTING"],
            "toAccountNum": goal["account_num"],
            "toRoutingNum": app.config["LOCAL_ROUTING"],
            "amount": amount,
            "uuid": str(req["uuid"]),
        }
        try:
            resp = requests.post(
                app.config["TRANSACTIONS_URI"], json=transaction,
                headers=headers, timeout=timeout)
        except requests.exceptions.RequestException as err:
            app.logger.error("Ledger request failed: %s", str(err))
            return "the ledger is unavailable", 502
        if resp.status_code != 201:
            app.logger.error("Ledger rejected the transfer: %s", resp.status_code)
            status = 400 if resp.status_code < 500 else 502
            return resp.text or "transfer failed", status
        goals_db.add_saved(username, goal_id, amount)
        return jsonify(goals_db.get_goal(username, goal_id)), 201

    @atexit.register
    def _shutdown():
        """Executed when web app is terminated."""
        app.logger.info("Stopping savingsgoals service.")

    app.logger.handlers = logging.getLogger("gunicorn.error").handlers
    app.logger.setLevel(logging.getLogger("gunicorn.error").level)
    add_trace_context(logging.getLogger('gunicorn.error'), app.logger)
    app.logger.info("Starting savingsgoals service.")

    if os.environ.get('ENABLE_TRACING') == "true":
        app.logger.info("✅ Tracing enabled.")
        trace.set_tracer_provider(TracerProvider())
        trace.get_tracer_provider().add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter()))
        set_global_textmap(TraceContextTextMapPropagator())
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
    else:
        app.logger.info("🚫 Tracing disabled.")

    app.config["VERSION"] = os.environ.get("VERSION")
    app.config["LOCAL_ROUTING"] = os.environ.get("LOCAL_ROUTING_NUM")
    app.config["PUBLIC_KEY"] = open(os.environ.get("PUB_KEY_PATH"), "r").read()
    app.config["BACKEND_TIMEOUT"] = int(os.environ.get("BACKEND_TIMEOUT", "4"))
    app.config["TRANSACTIONS_URI"] = "http://{}/transactions".format(
        os.environ.get("TRANSACTIONS_API_ADDR"))
    app.config["BALANCES_URI"] = "http://{}/balances".format(
        os.environ.get("BALANCES_API_ADDR"))

    try:
        goals_db = GoalsDb(os.environ.get("ACCOUNTS_DB_URI"), app.logger)
    except OperationalError:
        app.logger.critical("database connection failed")
        sys.exit(1)
    return app


if __name__ == "__main__":
    GOALS = create_app()
    GOALS.run()
