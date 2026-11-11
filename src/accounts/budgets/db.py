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
db manages interactions with the underlying database
"""

import logging
from sqlalchemy import create_engine, text
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# The accounts-db init scripts only run on a fresh database, so the service
# creates its own table when it starts. Portable SQL (Postgres, and SQLite
# for the unit tests).
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS budgets (
  username VARCHAR(64) PRIMARY KEY,
  limit_cents BIGINT NOT NULL CHECK (limit_cents > 0),
  FOREIGN KEY (username) REFERENCES users(username)
)
"""

UPSERT = """
INSERT INTO budgets (username, limit_cents) VALUES (:username, :limit_cents)
ON CONFLICT (username) DO UPDATE SET limit_cents = excluded.limit_cents
"""


class BudgetsDb:
    """
    BudgetsDb provides a set of helper functions over SQLAlchemy
    to handle db operations for the budgets service.
    """

    def __init__(self, uri, logger=logging):
        self.engine = create_engine(uri)
        self.logger = logger

        # Set up tracing autoinstrumentation for sqlalchemy
        SQLAlchemyInstrumentor().instrument(
            engine=self.engine,
            service="budgets",
        )

    def create_table(self):
        """Create the budgets table if it is missing.

        Raises: SQLAlchemyError if there was an issue with the database
        """
        self.logger.debug("QUERY: %s", CREATE_TABLE)
        with self.engine.begin() as conn:
            conn.execute(text(CREATE_TABLE))

    def get_budget(self, username):
        """Get the monthly limit of the specified user.

        Params: username - the username of the user
        Return: the limit in whole cents, or None if the user has no budget
        Raises: SQLAlchemyError if there was an issue with the database
        """
        statement = text("SELECT limit_cents FROM budgets WHERE username = :username")
        self.logger.debug("QUERY: %s", str(statement))
        with self.engine.connect() as conn:
            row = conn.execute(statement, {"username": username}).fetchone()
        return None if row is None else int(row[0])

    def set_budget(self, username, limit_cents):
        """Create or update the monthly limit of the specified user.

        Params: username - the username of the user
                limit_cents - the monthly limit in whole cents
        Raises: SQLAlchemyError if there was an issue with the database
        """
        self.logger.debug("QUERY: %s", UPSERT)
        with self.engine.begin() as conn:
            conn.execute(text(UPSERT), {"username": username, "limit_cents": limit_cents})

    def clear_budget(self, username):
        """Remove the budget of the specified user. Does nothing if there is none.

        Params: username - the username of the user
        Raises: SQLAlchemyError if there was an issue with the database
        """
        statement = text("DELETE FROM budgets WHERE username = :username")
        self.logger.debug("QUERY: %s", str(statement))
        with self.engine.begin() as conn:
            conn.execute(statement, {"username": username})
