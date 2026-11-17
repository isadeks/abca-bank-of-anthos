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
import secrets
from sqlalchemy import (create_engine, MetaData, Table, Column, String,
                        BigInteger, Integer, func, select)
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor


class GoalsDb:
    """GoalsDb provides helper functions over SQLAlchemy for savings goals."""

    def __init__(self, uri, logger=logging):
        self.engine = create_engine(uri)
        self.logger = logger
        metadata = MetaData()
        self.goals_table = Table(
            "savings_goals",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("username", String(64), nullable=False, index=True),
            Column("name", String(40), nullable=False),
            Column("target_cents", BigInteger, nullable=False),
            Column("saved_cents", BigInteger, nullable=False, default=0),
            Column("account_num", String(10), nullable=False, unique=True),
        )
        # The table is owned by this service: create it when missing
        metadata.create_all(self.engine, checkfirst=True)
        SQLAlchemyInstrumentor().instrument(
            engine=self.engine, service="savingsgoals")

    @staticmethod
    def _row_to_goal(row):
        return {
            "id": row.id,
            "name": row.name,
            "target": row.target_cents,
            "saved": row.saved_cents,
            "account_num": row.account_num,
        }

    def get_goals(self, username):
        """List the goals of a user, oldest first.

        Raises: SQLAlchemyError if there was an issue with the database
        """
        table = self.goals_table
        statement = table.select().where(
            table.c.username == username).order_by(table.c.id)
        with self.engine.connect() as conn:
            return [self._row_to_goal(r) for r in conn.execute(statement)]

    def get_goal(self, username, goal_id):
        """Return one goal of a user, or None."""
        table = self.goals_table
        statement = table.select().where(
            (table.c.username == username) & (table.c.id == goal_id))
        with self.engine.connect() as conn:
            row = conn.execute(statement).first()
        return self._row_to_goal(row) if row else None

    def count_goals(self, username):
        """Number of goals a user has."""
        table = self.goals_table
        statement = select([func.count()]).select_from(table).where(
            table.c.username == username)
        with self.engine.connect() as conn:
            return conn.execute(statement).scalar()

    def add_goal(self, username, name, target_cents):
        """Create a goal with its own ledger account number; returns the goal."""
        # 10 digits starting with 7: distinct from the demo accounts
        account_num = "7" + "".join(
            str(secrets.randbelow(10)) for _ in range(9))
        statement = self.goals_table.insert().values(
            username=username, name=name, target_cents=target_cents,
            saved_cents=0, account_num=account_num)
        with self.engine.begin() as conn:
            result = conn.execute(statement)
            goal_id = result.inserted_primary_key[0]
        return {"id": goal_id, "name": name, "target": target_cents,
                "saved": 0, "account_num": account_num}

    def delete_goal(self, username, goal_id):
        """Delete a goal; returns True if it existed."""
        table = self.goals_table
        statement = table.delete().where(
            (table.c.username == username) & (table.c.id == goal_id))
        with self.engine.begin() as conn:
            return conn.execute(statement).rowcount > 0

    def add_saved(self, username, goal_id, cents):
        """Add to the saved amount of a goal."""
        table = self.goals_table
        statement = table.update().where(
            (table.c.username == username) & (table.c.id == goal_id)
        ).values(saved_cents=table.c.saved_cents + cents)
        with self.engine.begin() as conn:
            conn.execute(statement)
