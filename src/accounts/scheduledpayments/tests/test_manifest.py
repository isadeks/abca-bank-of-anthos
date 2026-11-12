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
The deployment of the scheduled payments service: it is the only pod that
mounts the private signing key, and only that one file of the secret.
"""

import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = next((p for p in HERE.parents
             if (p / "kubernetes-manifests").is_dir() and (p / "src").is_dir()), None)
MANIFESTS = ROOT / "kubernetes-manifests" if ROOT else None
needs_repo = unittest.skipIf(ROOT is None, "run from a copy of the service alone")


@needs_repo
class ManifestTest(unittest.TestCase):
    """Static checks of kubernetes-manifests/"""

    def text(self, name):
        """The text of a manifest"""
        return (MANIFESTS / name).read_text()

    def test_listed_in_the_kustomization(self):
        self.assertRegex(self.text("kustomization.yaml"), r"(?m)^\s*-\s*scheduledpayments\.yaml\s*$")

    def test_image_is_filled_in_by_ci(self):
        self.assertIn("image: abca-boa/scheduledpayments", self.text("scheduledpayments.yaml"))

    def test_address_is_in_the_shared_config(self):
        self.assertRegex(self.text("config.yaml"), r'SCHEDULES_API_ADDR:\s*"scheduledpayments:8080"')

    def test_no_other_service_gets_the_private_key(self):
        # besides userservice, which signs logins, no other pod mounts it
        for manifest in MANIFESTS.glob("*.yaml"):
            mounts_private = re.search(r"key:\s*jwtRS256\.key\s*$", manifest.read_text(), re.M)
            with self.subTest(manifest=manifest.name):
                self.assertEqual(bool(mounts_private),
                                 manifest.name in ("scheduledpayments.yaml", "userservice.yaml"))

    def test_private_key_mount_is_narrow(self):
        text = self.text("scheduledpayments.yaml")
        self.assertEqual(len(re.findall(r"key:\s*jwtRS256\.key\s*$", text, re.M)), 1)
        self.assertRegex(text, r"mountPath:\s*/etc/signing\s+name:\s*signingkey\s+readOnly:\s*true")
        # the secret volume lists the one item, with restrictive permissions
        volume = text.split("name: signingkey\n          secret:")[1]
        self.assertIn("defaultMode: 288", volume)
        self.assertEqual(len(re.findall(r"- key:", volume)), 1)

    def test_no_kubernetes_api_token(self):
        self.assertIn("automountServiceAccountToken: false", self.text("scheduledpayments.yaml"))

    def test_runs_unprivileged(self):
        text = self.text("scheduledpayments.yaml")
        for setting in ("runAsNonRoot: true", "readOnlyRootFilesystem: true", "privileged: false"):
            self.assertIn(setting, text)
