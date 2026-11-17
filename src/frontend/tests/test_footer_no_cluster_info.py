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
The page footer no longer shows the cluster, pod and zone line.
"""

from test_payment_deposit_handlers import HandlerTestCase, backend_response


class TestFooterNoClusterInfo(HandlerTestCase):
    """The footer does not expose deployment details"""

    def test_footer_has_no_cluster_pod_zone(self):
        """a rendered page has no Cluster/Pod/Zone line"""
        self.post.return_value = backend_response(400, 'nope')
        html = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='a' * 31).get_data(as_text=True)
        self.assertIn('<footer', html)
        self.assertNotIn('Cluster: ', html)
        self.assertNotIn('Zone: ', html)
