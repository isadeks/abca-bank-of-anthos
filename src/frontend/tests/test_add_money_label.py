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
The home page's Deposit action is labelled "Add money".
"""

from test_payment_deposit_handlers import HandlerTestCase, backend_response


class TestAddMoneyLabel(HandlerTestCase):
    """The deposit button and dialog title read "Add money" """

    def test_button_and_title_say_add_money(self):
        """a rendered home page has no 'Deposit Funds' or 'Make a Deposit'"""
        self.post.return_value = backend_response(400, 'nope')
        html = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='a' * 31).get_data(as_text=True)
        self.assertIn('Add money', html)
        self.assertIn('id="exampleModalLongTitle">Add money<', html)
        self.assertNotIn('Deposit Funds', html)
        self.assertNotIn('Make a Deposit', html)
