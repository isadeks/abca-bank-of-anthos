# Copyright 2020 Google LLC
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
from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean, false
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor


class ContactsDb:
    """
    ContactsDb provides a set of helper functions over SQLAlchemy
    to handle db operations for contact service.
    """

    def __init__(self, uri, logger=logging):
        self.engine = create_engine(uri)
        self.logger = logger
        self.contacts_table = Table(
            "contacts",
            MetaData(),
            Column("username", String, nullable=False),
            Column("label", String, nullable=False),
            Column("account_num", String, nullable=False),
            Column("routing_num", String, nullable=False),
            Column("is_external", Boolean, nullable=False),
            Column("is_favorite", Boolean, nullable=False, default=False,
                   server_default=false()),
        )

        # Set up tracing autoinstrumentation for sqlalchemy
        SQLAlchemyInstrumentor().instrument(
            engine=self.engine,
            service="contacts",
        )

    def add_contact(self, contact):
        """Add a contact under the specified username.

        Params: user - a key/value dict of attributes describing a new contact
                    {'username': username, 'label': label, ...}
        Raises: SQLAlchemyError if there was an issue with the database
        """
        statement = self.contacts_table.insert().values(contact)
        self.logger.debug("QUERY: %s", str(statement))
        with self.engine.begin() as conn:
            conn.execute(statement)

    def get_contacts(self, username, include_favorite=False):
        """Get a list of contacts for the specified username.

        Params: username - the username of the user
                include_favorite - also return each contact's is_favorite flag
        Return: a list of contacts in the form of key/value attribute dicts,
                [ {'label': contact1, ...}, {'label': contact2, ...}, ...]
        Raises: SQLAlchemyError if there was an issue with the database
        """
        contacts = list()
        statement = self.contacts_table.select().where(
            self.contacts_table.c.username == username
        )
        self.logger.debug("QUERY: %s", str(statement))
        with self.engine.connect() as conn:
            for row in conn.execute(statement):
                contact = {
                    "label": row.label,
                    "account_num": row.account_num,
                    "routing_num": row.routing_num,
                    "is_external": row.is_external,
                }
                if include_favorite:
                    contact["is_favorite"] = bool(row.is_favorite)
                contacts.append(contact)
        self.logger.debug("RESULT: Fetched %d contacts.", len(contacts))
        return contacts

    def set_favorite(self, username, label, is_favorite):
        """Switch the favourite flag of one contact on or off.

        Params: username - the owner of the contact
                label - the label of the contact
                is_favorite - the new value of the flag
        Return: True if the contact exists, False otherwise
        Raises: SQLAlchemyError if there was an issue with the database
        """
        table = self.contacts_table
        statement = (
            table.update()
            .where(table.c.username == username)
            .where(table.c.label == label)
            .values(is_favorite=bool(is_favorite))
        )
        self.logger.debug("QUERY: %s", str(statement))
        with self.engine.begin() as conn:
            result = conn.execute(statement)
        return result.rowcount > 0
