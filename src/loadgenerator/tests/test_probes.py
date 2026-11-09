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
The load generator must expose Locust's web interface (the only HTTP endpoint it
has) and the manifests must probe it, so a hung load generator is restarted.

Only the standard library is used.
"""

import re
import unittest
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
WEB_PORT = "8089"

MANIFESTS = [SERVICE_DIR / "k8s" / "base" / "loadgenerator.yaml"]
for parent in SERVICE_DIR.parents:
    if (parent / "kubernetes-manifests").is_dir():
        MANIFESTS.append(parent / "kubernetes-manifests" / "loadgenerator.yaml")
        break


def probe(text, name):
    """The lines of the `<name>:` probe block, or None if there is none."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == f"{name}:":
            indent = len(line) - len(line.lstrip())
            out = []
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                out.append(nxt.strip())
            return out
    return None


class DockerfileTest(unittest.TestCase):
    def setUp(self):
        self.dockerfile = (SERVICE_DIR / "Dockerfile").read_text()

    def test_locust_serves_its_web_interface_for_probes(self):
        entrypoint = re.search(r"^ENTRYPOINT\s+(.*)$", self.dockerfile, re.M).group(1)
        self.assertIn(f"--web-port {WEB_PORT}", entrypoint)

    def test_load_test_starts_without_a_click(self):
        entrypoint = re.search(r"^ENTRYPOINT\s+(.*)$", self.dockerfile, re.M).group(1)
        self.assertIn("--autostart", entrypoint)
        self.assertNotIn("--headless", entrypoint)  # headless has no web interface to probe


class ManifestProbeTest(unittest.TestCase):
    def test_liveness_and_readiness_probes_hit_the_web_interface(self):
        for manifest in MANIFESTS:
            text = manifest.read_text()
            for name in ("livenessProbe", "readinessProbe"):
                with self.subTest(manifest=str(manifest.name), probe=name):
                    block = probe(text, name)
                    self.assertIsNotNone(block, f"{manifest} has no {name}")
                    self.assertIn("httpGet:", block)
                    self.assertIn("path: /", block)
                    self.assertIn(f"port: {WEB_PORT}", block)

    def test_probes_have_a_start_up_delay_and_timeout(self):
        for manifest in MANIFESTS:
            text = manifest.read_text()
            for name in ("livenessProbe", "readinessProbe"):
                with self.subTest(manifest=str(manifest.name), probe=name):
                    block = " ".join(probe(text, name))
                    self.assertRegex(block, r"initialDelaySeconds: \d+")
                    self.assertRegex(block, r"timeoutSeconds: \d+")

    def test_liveness_waits_longer_than_readiness_before_restarting(self):
        for manifest in MANIFESTS:
            text = manifest.read_text()
            delay = lambda name: int(re.search(r"initialDelaySeconds: (\d+)", " ".join(probe(text, name))).group(1))
            self.assertGreater(delay("livenessProbe"), delay("readinessProbe"))


if __name__ == "__main__":
    unittest.main()
