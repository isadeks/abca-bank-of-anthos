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

"""Web service for recurring (scheduled) payments.

Stores each customer's schedules and exposes create, list and cancel. A
background runner (see worker.py) sends the payments when they fall due.
"""

import atexit
import datetime
import logging
import os
import re
import sys
import uuid

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

from db import ScheduleDb
from signing import PaymentTokenSigner
from trace_logging import add_trace_context
from worker import FREQUENCIES, PaymentRunner, next_due_date, start_background

# 500,000.00 dollars, the same limit as a deposit in the web UI
MAX_AMOUNT_CENTS = 50_000_000
_ACCOUNT_RE = re.compile(r"\A[0-9]{10}\Z")


def _today():
    """Today's date; the day payments fall due is the UTC day."""
    return datetime.datetime.now(datetime.timezone.utc).date()


def _schedule_json(schedule):
    """The public view of a schedule."""
    def iso(value):
        return value.isoformat() if value is not None else None
    return {
        "id": schedule["schedule_id"],
        "account_num": schedule["to_account_num"],
        "label": schedule["to_label"],
        "amount": schedule["amount_cents"],
        "frequency": schedule["frequency"],
        "next_payment_date": iso(schedule["next_payment_date"]),
        "last_status": schedule["last_status"],
        "last_error": schedule["last_error"],
        "last_attempt_date": iso(schedule["last_attempt_date"]),
    }


# pylint: disable-msg=too-many-locals
def create_app():
    """Flask application factory to create instances
    of the Scheduled Payments Flask App
    """
    app = Flask(__name__)

    # Disabling unused-variable for lines with route decorated functions
    # as pylint thinks they are unused
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
        """The verified token payload; PermissionError or
        InvalidTokenError if the caller is not the user in the path."""
        auth_header = request.headers.get("Authorization")
        token = auth_header.split(" ")[-1] if auth_header else ""
        payload = jwt.decode(
            token, key=app.config["PUBLIC_KEY"], algorithms="RS256")
        if username != payload["user"]:
            raise PermissionError("token does not belong to this user")
        return payload

    @app.route("/schedules/<username>", methods=["GET"])
    def list_schedules(username):
        """List the authenticated user's scheduled payments."""
        try:
            _authenticate(username)
            schedules = schedule_db.list_schedules(username)
            return jsonify([_schedule_json(s) for s in schedules]), 200
        except (PermissionError, KeyError, jwt.exceptions.InvalidTokenError) as err:
            app.logger.error("Error listing schedules: %s", str(err))
            return "authentication denied", 401
        except SQLAlchemyError as err:
            app.logger.error("Error listing schedules: %s", str(err))
            return "failed to retrieve schedules", 500

    @app.route("/schedules/<username>", methods=["POST"])
    def create_schedule(username):
        """Schedule a recurring payment to one of the user's contacts.

        request fields:
        - account_num: the account of one of the user's (internal) contacts
        - amount: in cents, a positive integer
        - frequency: "weekly" or "monthly"

        The first payment is due one period (a week or a month) from today.
        """
        try:
            payload = _authenticate(username)
            req = request.get_json(silent=True)
            amount, frequency, account_num = _validate_request(req)
            contact = _find_contact(username, account_num)
            if contact["account_num"] == payload["acct"]:
                raise UserWarning("you can't schedule a payment to yourself")
            today = _today()
            schedule = schedule_db.create_schedule({
                "username": username,
                "from_account_num": payload["acct"],
                "to_account_num": contact["account_num"],
                "to_label": contact["label"],
                "amount_cents": amount,
                "frequency": frequency,
                "anchor_day": today.day,
                "next_payment_date": next_due_date(today, frequency, today.day),
            })
            app.logger.info("Successfully created a schedule.")
            return jsonify(_schedule_json(schedule)), 201
        except (PermissionError, KeyError, jwt.exceptions.InvalidTokenError) as err:
            app.logger.error("Error creating schedule: %s", str(err))
            return "authentication denied", 401
        except UserWarning as warn:
            app.logger.error("Error creating schedule: %s", str(warn))
            return str(warn), 400
        except requests.exceptions.RequestException as err:
            app.logger.error("Error checking contacts: %s", str(err))
            return "could not check the recipient", 502
        except SQLAlchemyError as err:
            app.logger.error("Error creating schedule: %s", str(err))
            return "failed to create schedule", 500

    @app.route("/schedules/<username>/<schedule_id>", methods=["DELETE"])
    def cancel_schedule(username, schedule_id):
        """Cancel one of the authenticated user's scheduled payments."""
        try:
            _authenticate(username)
            if not _is_uuid(schedule_id) or not schedule_db.cancel_schedule(
                    username, schedule_id):
                # also the answer for somebody else's schedule
                return "schedule not found", 404
            app.logger.info("Successfully cancelled a schedule.")
            return "", 204
        except (PermissionError, KeyError, jwt.exceptions.InvalidTokenError) as err:
            app.logger.error("Error cancelling schedule: %s", str(err))
            return "authentication denied", 401
        except SQLAlchemyError as err:
            app.logger.error("Error cancelling schedule: %s", str(err))
            return "failed to cancel schedule", 500

    def _is_uuid(value):
        try:
            return str(uuid.UUID(value)) == value
        except ValueError:
            return False

    def _validate_request(req):
        """Check the fields of a new schedule; UserWarning if invalid."""
        if not isinstance(req, dict):
            raise UserWarning("missing required field(s)")
        if any(f not in req for f in ("account_num", "amount", "frequency")):
            raise UserWarning("missing required field(s)")
        amount, frequency, account_num = (
            req["amount"], req["frequency"], req["account_num"])
        if (not isinstance(amount, int) or isinstance(amount, bool)
                or amount <= 0):
            raise UserWarning("amount must be a positive number of cents")
        if amount > MAX_AMOUNT_CENTS:
            raise UserWarning("amount is too large")
        if frequency not in FREQUENCIES:
            raise UserWarning("frequency must be weekly or monthly")
        if not isinstance(account_num, str) or not _ACCOUNT_RE.match(account_num):
            raise UserWarning("invalid account number")
        return amount, frequency, account_num

    def _find_contact(username, account_num):
        """The user's own contact with this account, as the contacts service
        reports it. UserWarning if there is none, or it is an external
        account (those can only deposit)."""
        auth_header = request.headers.get("Authorization")
        resp = requests.get(
            url=f"{app.config['CONTACTS_URI']}/{username}",
            headers={"Authorization": auth_header},
            timeout=app.config["BACKEND_TIMEOUT"])
        resp.raise_for_status()
        for contact in resp.json():
            if (contact.get("account_num") == account_num
                    and not contact.get("is_external")):
                return contact
        raise UserWarning("the recipient is not one of your contacts")

    @atexit.register
    def _shutdown():
        """Executed when web app is terminated."""
        app.logger.info("Stopping scheduled payments service.")

    # set up logger
    app.logger.handlers = logging.getLogger("gunicorn.error").handlers
    app.logger.setLevel(logging.getLogger("gunicorn.error").level)
    add_trace_context(logging.getLogger('gunicorn.error'), app.logger)
    app.logger.info("Starting scheduled payments service.")

    # Set up tracing and export spans over OTLP to the OpenTelemetry collector.
    if os.environ.get('ENABLE_TRACING') == "true":
        app.logger.info("✅ Tracing enabled.")
        trace.set_tracer_provider(TracerProvider())
        otlp_exporter = OTLPSpanExporter()
        trace.get_tracer_provider().add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
        # W3C trace context (traceparent) between services
        set_global_textmap(TraceContextTextMapPropagator())
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
    else:
        app.logger.info("🚫 Tracing disabled.")

    # setup global variables
    app.config["VERSION"] = os.environ.get("VERSION")
    app.config["PUBLIC_KEY"] = open(os.environ.get("PUB_KEY_PATH"), "r").read()
    app.config["CONTACTS_URI"] = "http://{}/contacts".format(
        os.environ.get("CONTACTS_API_ADDR"))
    app.config["BACKEND_TIMEOUT"] = int(os.environ.get("BACKEND_TIMEOUT", "4"))

    # Configure database connection
    try:
        schedule_db = ScheduleDb(os.environ.get("ACCOUNTS_DB_URI"), app.logger)
        schedule_db.create_tables()
    except OperationalError:
        app.logger.critical("database connection failed")
        sys.exit(1)

    # The runner that sends the payments when they fall due
    if os.environ.get("ENABLE_RUNNER", "true") == "true":
        # The signing key is read here and handed to the signer only; it is
        # not kept in the app config or logged.
        with open(os.environ.get("PRIV_KEY_PATH"), "r") as key_file:
            signer = PaymentTokenSigner(key_file.read())
        runner = PaymentRunner(
            schedule_db, signer,
            transactions_uri="http://{}/transactions".format(
                os.environ.get("TRANSACTIONS_API_ADDR")),
            local_routing=os.environ.get("LOCAL_ROUTING_NUM"),
            logger=app.logger,
            timeout=app.config["BACKEND_TIMEOUT"])
        app.config["RUNNER"] = runner
        interval = int(os.environ.get("RUNNER_INTERVAL_SECONDS", "60"))
        app.config["RUNNER_STOP"] = start_background(runner, interval)
        atexit.register(app.config["RUNNER_STOP"].set)
    return app


if __name__ == "__main__":
    # Create an instance of flask server when called directly
    SCHEDULES = create_app()
    SCHEDULES.run()
