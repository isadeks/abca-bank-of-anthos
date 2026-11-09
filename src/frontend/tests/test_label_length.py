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
The contacts service's "label too long" message is shown to the user.
"""

from test_payment_deposit_handlers import HandlerTestCase, backend_response

TOO_LONG = 'label must be 30 characters or fewer'


class TestLabelTooLong(HandlerTestCase):
    """A rejected label is reported on the page and nothing is sent"""

    def test_payment_shows_label_error(self):
        """the payment fails with the contacts service's message"""
        self.post.return_value = backend_response(400, TOO_LONG)
        resp = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='a' * 31)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Payment failed: ' + TOO_LONG,
                      resp.get_data(as_text=True))
        self.assertEqual(self.ledger_calls(), [])

    def test_deposit_shows_label_error(self):
        """the deposit fails with the contacts service's message"""
        self.post.return_value = backend_response(400, TOO_LONG)
        resp = self.deposit(account='add',
                            external_account_num='7777777777',
                            external_routing_num='123456789',
                            external_label='a' * 31)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Deposit failed: ' + TOO_LONG,
                      resp.get_data(as_text=True))
        self.assertEqual(self.ledger_calls(), [])
