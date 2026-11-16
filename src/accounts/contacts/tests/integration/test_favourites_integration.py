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
Integration tests for favourite contacts against the real accounts-db.
"""

LOCAL_ROUTING_NUM = '883745000'


def _add(client, username, auth_header, label='Mom', account='1033623433'):
    contact = {'label': label, 'account_num': account,
               'routing_num': LOCAL_ROUTING_NUM, 'is_external': False}
    assert client.post('/contacts/' + username, json=contact,
                       headers=auth_header).status_code == 201


def test_new_contact_is_not_a_favourite(client, user, auth_header):
    """The column defaults to false, so contacts added without it keep working."""
    username, _ = user
    _add(client, username, auth_header)

    listed = client.get('/contacts/' + username, headers=auth_header).get_json()

    assert [c['is_favourite'] for c in listed] == [False]


def test_favourite_can_be_switched_on_and_off(client, user, auth_header):
    """The flag round-trips through Postgres."""
    username, _ = user
    _add(client, username, auth_header)
    url = '/contacts/' + username + '/Mom/favourite'

    on = client.put(url, json={'is_favourite': True}, headers=auth_header)
    assert on.status_code == 200
    listed = client.get('/contacts/' + username, headers=auth_header).get_json()
    assert listed[0]['is_favourite'] is True

    off = client.put(url, json={'is_favourite': False}, headers=auth_header)
    assert off.status_code == 200
    listed = client.get('/contacts/' + username, headers=auth_header).get_json()
    assert listed[0]['is_favourite'] is False


def test_only_the_named_contact_changes(client, user, auth_header):
    """Other contacts of the user keep their setting."""
    username, _ = user
    _add(client, username, auth_header, 'Mom', '1033623433')
    _add(client, username, auth_header, 'Dad', '1055757655')

    client.put('/contacts/' + username + '/Dad/favourite',
               json={'is_favourite': True}, headers=auth_header)

    listed = client.get('/contacts/' + username, headers=auth_header).get_json()
    assert {c['label']: c['is_favourite'] for c in listed} == {'Mom': False, 'Dad': True}


def test_unknown_contact_is_404(client, user, auth_header):
    """Switching a contact that does not exist is reported."""
    username, _ = user
    response = client.put('/contacts/' + username + '/Ghost/favourite',
                          json={'is_favourite': True}, headers=auth_header)
    assert response.status_code == 404


def test_demo_favourites_in_the_database_image(contacts_db):
    """The demo data marks some of testuser's contacts as favourites."""
    contacts = {c['label']: c for c in contacts_db.get_contacts('testuser', True)}

    assert contacts['Alice']['is_favourite'] is True
    assert contacts['Bob']['is_favourite'] is False
