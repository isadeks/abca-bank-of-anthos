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
Integration tests for savings accounts against the real accounts-db
(Postgres with the Bank of Anthos schema and demo data).
"""

import pytest
from sqlalchemy import text

PASSWORD = 'correct horse battery staple'


def user_form(username):
    """Sign-up form fields the frontend posts to userservice."""
    return {
        'username': username,
        'password': PASSWORD,
        'password-repeat': PASSWORD,
        'firstname': 'Integration',
        'lastname': 'Test',
        'birthday': '1990-02-03',
        'timezone': '-5',
        'address': '1 Test Street',
        'state': 'NY',
        'zip': '10004',
        'ssn': '123-45-6789',
    }


@pytest.fixture
def savings_username(users_db, new_username):
    """A unique username whose savings account row is removed afterwards."""
    yield new_username
    with users_db.engine.begin() as conn:
        conn.execute(
            text('DELETE FROM savings_accounts WHERE username = :u'),
            {'u': new_username})


def test_user_can_open_one_savings_account(client, users_db, savings_username):
    """A savings account is stored in Postgres and returned for its owner."""
    assert client.post('/users', data=user_form(savings_username)).status_code == 201
    assert client.get(f'/users/{savings_username}/savings').status_code == 404

    opened = client.post(f'/users/{savings_username}/savings')

    assert opened.status_code == 201
    accountid = opened.get_json()['accountid']
    assert len(accountid) == 10 and accountid.isdigit()
    assert users_db.get_savings_account(savings_username) == accountid
    fetched = client.get(f'/users/{savings_username}/savings')
    assert fetched.get_json() == {'accountid': accountid}
    assert client.post(f'/users/{savings_username}/savings').status_code == 409


def test_unknown_user_cannot_open_a_savings_account(client, savings_username):
    """Only users that exist can open a savings account."""
    assert client.post(f'/users/{savings_username}/savings').status_code == 404
