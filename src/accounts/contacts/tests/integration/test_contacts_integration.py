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
Integration tests for the contacts service against the real accounts-db
(Postgres with the Bank of Anthos schema and demo data).
"""

import jwt

LOCAL_ROUTING_NUM = '883745000'


def test_added_contact_is_listed(client, user, auth_header):
    """A contact added with POST shows up in the GET list with all its fields."""
    username, _ = user
    contact = {
        'label': 'Mom',
        'account_num': '1033623433',
        'routing_num': LOCAL_ROUTING_NUM,
        'is_external': False,
    }

    added = client.post('/contacts/' + username, json=contact, headers=auth_header)
    assert added.status_code == 201

    listed = client.get('/contacts/' + username, headers=auth_header)
    assert listed.status_code == 200
    assert listed.get_json() == [contact]


def test_external_contact_keeps_its_flag(client, user, auth_header):
    """The boolean is_external column round-trips through Postgres."""
    username, _ = user
    internal = {
        'label': 'Friend', 'account_num': '1055757655',
        'routing_num': LOCAL_ROUTING_NUM, 'is_external': False}
    external = {
        'label': 'Other Bank', 'account_num': '9099791699',
        'routing_num': '808889588', 'is_external': True}
    assert client.post('/contacts/' + username, json=internal,
                       headers=auth_header).status_code == 201
    assert client.post('/contacts/' + username, json=external,
                       headers=auth_header).status_code == 201

    listed = client.get('/contacts/' + username, headers=auth_header).get_json()

    assert sorted(listed, key=lambda c: c['label']) == [internal, external]


def test_contacts_are_per_user(client, contacts_db, user, auth_header):
    """The list only holds the contacts of the authenticated user."""
    username, _ = user
    client.post('/contacts/' + username, headers=auth_header, json={
        'label': 'Mom', 'account_num': '1033623433',
        'routing_num': LOCAL_ROUTING_NUM, 'is_external': False})

    assert len(contacts_db.get_contacts(username)) == 1
    # The demo user's contacts are not mixed in.
    assert all(c['label'] != 'Mom' for c in contacts_db.get_contacts('testuser'))


def test_duplicate_label_is_conflict(client, user, auth_header):
    """The service reads existing contacts from the database to reject duplicates."""
    username, _ = user
    contact = {
        'label': 'Mom', 'account_num': '1033623433',
        'routing_num': LOCAL_ROUTING_NUM, 'is_external': False}
    assert client.post('/contacts/' + username, json=contact,
                       headers=auth_header).status_code == 201

    again = client.post('/contacts/' + username, json=dict(contact, account_num='1055757655'),
                        headers=auth_header)

    assert again.status_code == 409


def test_contact_for_unknown_user_is_rejected_by_the_schema(client, keys):
    """contacts.username is a foreign key to users.username."""
    token = jwt.encode({'user': 'it_nobody_here', 'acct': '1000000000'}, keys['private'],
                       algorithm='RS256')

    response = client.post(
        '/contacts/it_nobody_here', headers={'Authorization': 'Bearer ' + token},
        json={'label': 'Mom', 'account_num': '1033623433',
              'routing_num': LOCAL_ROUTING_NUM, 'is_external': False})

    assert response.status_code == 500


def test_demo_contacts_exist_in_the_database_image(contacts_db):
    """The accounts-db image ships demo contacts for the demo users."""
    contacts = {c['label']: c for c in contacts_db.get_contacts('testuser')}

    assert {'Alice', 'Bob', 'Eve', 'External Bank'} <= set(contacts)
    assert contacts['External Bank']['is_external'] is True
    assert contacts['Alice']['account_num'] == '1033623433'
