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
Integration tests for userservice against the real accounts-db
(Postgres with the Bank of Anthos schema and demo data).
"""

import bcrypt
import jwt

PASSWORD = 'correct horse battery staple'


def user_form(username, password=PASSWORD):
    """Sign-up form fields the frontend posts to userservice."""
    return {
        'username': username,
        'password': password,
        'password-repeat': password,
        'firstname': 'Integration',
        'lastname': 'Test',
        'birthday': '1990-02-03',
        'timezone': '-5',
        'address': '1 Test Street',
        'state': 'NY',
        'zip': '10004',
        'ssn': '123-45-6789',
    }


def test_created_user_can_log_in(client, users_db, new_username, key_files):
    """A user created through POST /users can log in with the same password."""
    created = client.post('/users', data=user_form(new_username))
    assert created.status_code == 201

    login = client.get('/login', query_string={
        'username': new_username, 'password': PASSWORD})
    assert login.status_code == 200

    stored = users_db.get_user(new_username)
    with open(key_files[1], 'r', encoding='utf-8') as pub_file:
        public_key = pub_file.read()
    claims = jwt.decode(login.get_json()['token'], key=public_key, algorithms='RS256')
    assert claims['user'] == new_username
    assert claims['acct'] == stored['accountid']
    assert claims['name'] == 'Integration Test'


def test_created_user_is_stored_with_schema_types(users_db, client, new_username):
    """The row written to Postgres has the expected shape and a bcrypt hash."""
    client.post('/users', data=user_form(new_username))

    stored = users_db.get_user(new_username)

    assert stored['username'] == new_username
    assert len(stored['accountid'].strip()) == 10
    assert stored['accountid'].strip().isdigit()
    assert stored['firstname'] == 'Integration'
    assert stored['birthday'].isoformat() == '1990-02-03'
    assert stored['state'] == 'NY'
    assert stored['ssn'] == '123-45-6789'
    assert bcrypt.checkpw(PASSWORD.encode('utf-8'), bytes(stored['passhash']))


def test_login_with_wrong_password_is_unauthorized(client, new_username):
    """The password is checked against the hash read back from the database."""
    client.post('/users', data=user_form(new_username))

    login = client.get('/login', query_string={
        'username': new_username, 'password': 'not the password'})

    assert login.status_code == 401


def test_login_unknown_user_is_not_found(client, new_username):
    """A username that was never created is reported as missing."""
    login = client.get('/login', query_string={
        'username': new_username, 'password': PASSWORD})

    assert login.status_code == 404


def test_duplicate_username_is_conflict(client, new_username):
    """The users table does not get a second row for the same username."""
    assert client.post('/users', data=user_form(new_username)).status_code == 201

    again = client.post('/users', data=user_form(new_username))

    assert again.status_code == 409


def test_demo_user_exists_in_the_database_image(users_db):
    """The accounts-db image ships the demo users the load generator logs in with."""
    stored = users_db.get_user('testuser')

    assert stored is not None
    assert stored['accountid'].strip() == '1011226111'
