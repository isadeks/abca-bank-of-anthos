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
Unit tests for deposit amounts with more than two decimal places: they are
rejected with a clear message instead of being rounded (DEM-270).
"""

from test_payment_deposit_handlers import HandlerTestCase


class TestDepositDecimals(HandlerTestCase):
    """/deposit amount precision"""

    def test_more_than_two_decimals_is_rejected(self):
        """10.005 gives 400, a clear message, and sends nothing"""
        for amount in ('10.005', '10.001', '0.999', '1.234567'):
            with self.subTest(amount=amount):
                resp = self.deposit(amount=amount)
                self.assertEqual(resp.status_code, 400)
                body = resp.get_data(as_text=True)
                self.assertIn(
                    f'Deposit failed: {amount} has more than two decimal '
                    'places', body)
                self.assertIn('text-danger', body)
        self.post.assert_not_called()
        self.sleep.assert_not_called()

    def test_rejected_amount_does_not_save_the_contact(self):
        """a bad amount stops a deposit from a new account before the
        contact is created"""
        resp = self.client.post('/deposit', data={
            'account': 'add', 'external_account_num': '1111111111',
            'external_routing_num': '123456789', 'external_label': 'Other',
            'amount': '10.005', 'uuid': 'u2'})
        self.assertEqual(resp.status_code, 400)
        self.post.assert_not_called()

    def test_up_to_two_decimals_is_accepted_exactly(self):
        """amounts with at most two significant decimals are sent unchanged"""
        for amount, cents in (('10', 1000), ('10.5', 1050), ('10.05', 1005),
                              ('10.00', 1000), ('10.000', 1000),
                              ('0.01', 1), ('19.99', 1999)):
            with self.subTest(amount=amount):
                self.post.reset_mock()
                resp = self.deposit(amount=amount)
                self.assertEqual(resp.status_code, 303)
                calls = self.ledger_calls()
                self.assertEqual(self.sent(calls[0])['amount'], cents)
