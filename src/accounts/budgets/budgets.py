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

"""Web service for handling users' monthly budgets.

Stores one monthly spending limit per user, in whole cents.
"""

import atexit
import logging
import os
import sys

import jwt
from flask import Flask, jsonify, request
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.propagate import set_global_textmap
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from db import BudgetsDb

# Largest accepted limit: 1 billion dollars, in cents.
# The frontend uses the same bound (spend_budget.MAX_LIMIT_CENTS).
MAX_LIMIT_CENTS = 100_000_000_000


def create_app():
    """Flask application factory to create instances
    of the Budgets Service Flask App
    """
    app = Flask(__name__)

    # Disabling unused-variable for lines with route decorated functions
    # as pylint thinks they are unused
    # pylint: disable=unused-variable

    @app.route("/version", methods=["GET"])
    def version():
        """
        Service version endpoint
        """
        return app.config["VERSION"], 200

    @app.route("/ready", methods=["GET"])
    def ready():
        """Readiness probe."""
        return "ok", 200

    def _authenticate(username):
        """Check the login token and that it belongs to username.

        Raises: PermissionError or jwt.exceptions.InvalidTokenError
        """
        auth_header = request.headers.get("Authorization")
        if auth_header:
            token = auth_header.split(" ")[-1]
        else:
            token = ""
        auth_payload = jwt.decode(
            token, key=app.config["PUBLIC_KEY"], algorithms="RS256"
        )
        if username != auth_payload["user"]:
            raise PermissionError

    @app.route("/budget/<username>", methods=["GET"])
    def get_budget(username):
        """Retrieve the monthly budget of the authenticated user.

        Return: {"limit_cents": <int>}, or {"limit_cents": null} if none is set
        """
        try:
            _authenticate(username)
            limit_cents = budgets_db.get_budget(username)
            app.logger.debug("Successfully retrieved budget.")
            return jsonify({"limit_cents": limit_cents}), 200
        except (PermissionError, jwt.exceptions.InvalidTokenError) as err:
            app.logger.error("Error retrieving budget: %s", str(err))
            return "authentication denied", 401
        except SQLAlchemyError as err:
            app.logger.error("Error retrieving budget: %s", str(err))
            return "failed to retrieve budget", 500

    @app.route("/budget/<username>", methods=["PUT"])
    def set_budget(username):
        """Set (create or update) the monthly budget of the authenticated user.

        request fields:
        - limit_cents: whole cents, an integer from 1 to 100000000000

        Return: {"limit_cents": <int>}
        """
        try:
            _authenticate(username)
            limit_cents = _validate_limit(request.get_json(silent=True))
            budgets_db.set_budget(username, limit_cents)
            app.logger.info("Successfully set budget.")
            return jsonify({"limit_cents": limit_cents}), 200
        except (PermissionError, jwt.exceptions.InvalidTokenError) as err:
            app.logger.error("Error setting budget: %s", str(err))
            return "authentication denied", 401
        except UserWarning as warn:
            app.logger.error("Error setting budget: %s", str(warn))
            return str(warn), 400
        except SQLAlchemyError as err:
            app.logger.error("Error setting budget: %s", str(err))
            return "failed to set budget", 500

    @app.route("/budget/<username>", methods=["DELETE"])
    def clear_budget(username):
        """Clear the monthly budget of the authenticated user.

        Succeeds also if no budget was set.
        """
        try:
            _authenticate(username)
            budgets_db.clear_budget(username)
            app.logger.info("Successfully cleared budget.")
            return "", 204
        except (PermissionError, jwt.exceptions.InvalidTokenError) as err:
            app.logger.error("Error clearing budget: %s", str(err))
            return "authentication denied", 401
        except SQLAlchemyError as err:
            app.logger.error("Error clearing budget: %s", str(err))
            return "failed to clear budget", 500

    def _validate_limit(req):
        """Check that this request holds a valid limit and return it"""
        if not isinstance(req, dict) or "limit_cents" not in req:
            raise UserWarning("missing required field(s)")
        limit_cents = req["limit_cents"]
        # bool is a subclass of int, but true is not an amount
        if isinstance(limit_cents, bool) or not isinstance(limit_cents, int):
            raise UserWarning("limit_cents must be a whole number of cents")
        if limit_cents < 1 or limit_cents > MAX_LIMIT_CENTS:
            raise UserWarning("limit_cents out of range")
        return limit_cents

    @atexit.register
    def _shutdown():
        """Executed when web app is terminated."""
        app.logger.info("Stopping budgets service.")

    # set up logger
    app.logger.handlers = logging.getLogger("gunicorn.error").handlers
    app.logger.setLevel(logging.getLogger("gunicorn.error").level)
    app.logger.info("Starting budgets service.")

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

    # setup global variables
    app.config["VERSION"] = os.environ.get("VERSION")
    app.config["PUBLIC_KEY"] = open(os.environ.get("PUB_KEY_PATH"), "r").read()

    # Configure database connection and make sure the table exists
    try:
        budgets_db = BudgetsDb(os.environ.get("ACCOUNTS_DB_URI"), app.logger)
        budgets_db.create_table()
    except OperationalError:
        app.logger.critical("database connection failed")
        sys.exit(1)
    return app


if __name__ == "__main__":
    # Create an instance of flask server when called directly
    BUDGETS = create_app()
    BUDGETS.run()
