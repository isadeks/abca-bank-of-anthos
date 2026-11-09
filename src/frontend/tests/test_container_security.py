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
Every application service must run as a non-root user (uid/gid 1000) with a
read-only root filesystem: the image declares the user, and the manifest sets
runAsNonRoot/runAsUser, readOnlyRootFilesystem and a writable /tmp volume.

Only the standard library is used so the check runs in any service's test env.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFESTS = ROOT / "kubernetes-manifests"

# service -> (image definition, manifest, deployment name)
PYTHON_SERVICES = {
    "frontend": ("src/frontend/Dockerfile", "frontend.yaml"),
    "userservice": ("src/accounts/userservice/Dockerfile", "userservice.yaml"),
    "contacts": ("src/accounts/contacts/Dockerfile", "contacts.yaml"),
    "loadgenerator": ("src/loadgenerator/Dockerfile", "loadgenerator.yaml"),
}
JAVA_SERVICES = {
    "ledgerwriter": ("src/ledger/ledgerwriter/pom.xml", "ledger-writer.yaml"),
    "balancereader": ("src/ledger/balancereader/pom.xml", "balance-reader.yaml"),
    "transactionhistory": ("src/ledger/transactionhistory/pom.xml", "transaction-history.yaml"),
}
ALL_SERVICES = {**PYTHON_SERVICES, **JAVA_SERVICES}


def block(lines, start):
    """Return the 'key: value' children (as a dict of stripped lines) of the
    mapping whose key is on lines[start]."""
    indent = len(lines[start]) - len(lines[start].lstrip())
    out = []
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        out.append(line.strip())
    return out


def parse_manifest(name):
    """Pod-level securityContext, container securityContext and volume info of
    the single Deployment in a manifest."""
    text = (MANIFESTS / name).read_text()
    deployment = next(d for d in text.split("\n---") if re.search(r"^kind: Deployment$", d, re.M))
    lines = deployment.splitlines()
    pod, container, mounts, volumes = None, None, None, None
    for i, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped == "securityContext:" and indent == 6:
            pod = block(lines, i)
        elif stripped == "securityContext:" and indent == 10:
            container = block(lines, i)
        elif stripped == "volumeMounts:" and indent == 10:
            mounts = block(lines, i)
        elif stripped == "volumes:" and indent == 6:
            volumes = block(lines, i)
    return pod, container, mounts, volumes


class ImageDefinitionTest(unittest.TestCase):
    def test_python_dockerfiles_declare_a_non_root_user(self):
        for service, (path, _) in PYTHON_SERVICES.items():
            with self.subTest(service=service):
                dockerfile = (ROOT / path).read_text()
                users = re.findall(r"^USER\s+(\S+)\s*$", dockerfile, re.M)
                self.assertTrue(users, f"{path} has no USER instruction")
                # the last USER is the one the container runs as
                self.assertEqual(users[-1], "1000:1000")
                # created with the same fixed ids, so the name resolves too
                self.assertRegex(dockerfile, r"groupadd\s+--gid\s+1000")
                self.assertRegex(dockerfile, r"useradd\s+--uid\s+1000\s+--gid\s+1000")

    def test_python_dockerfiles_do_not_write_bytecode(self):
        for service, (path, _) in PYTHON_SERVICES.items():
            with self.subTest(service=service):
                self.assertIn("PYTHONDONTWRITEBYTECODE=1", (ROOT / path).read_text())

    def test_jib_images_declare_a_non_root_user(self):
        for service, (path, _) in JAVA_SERVICES.items():
            with self.subTest(service=service):
                pom = (ROOT / path).read_text()
                jib = pom[pom.index("jib-maven-plugin"):]
                jib = jib[:jib.index("</plugin>")]
                self.assertRegex(jib, r"<container>[\s\S]*<user>1000:1000</user>[\s\S]*</container>")


class ManifestTest(unittest.TestCase):
    def test_pod_runs_as_non_root_uid_1000(self):
        for service, (_, manifest) in ALL_SERVICES.items():
            with self.subTest(service=service):
                pod, _, _, _ = parse_manifest(manifest)
                self.assertIsNotNone(pod, f"{manifest} has no pod securityContext")
                self.assertIn("runAsNonRoot: true", pod)
                self.assertIn("runAsUser: 1000", pod)
                self.assertIn("runAsGroup: 1000", pod)

    def test_container_has_read_only_root_filesystem(self):
        for service, (_, manifest) in ALL_SERVICES.items():
            with self.subTest(service=service):
                _, container, _, _ = parse_manifest(manifest)
                self.assertIsNotNone(container, f"{manifest} has no container securityContext")
                self.assertIn("readOnlyRootFilesystem: true", container)
                self.assertIn("allowPrivilegeEscalation: false", container)
                self.assertIn("privileged: false", container)

    def test_only_the_mounted_volumes_are_writable(self):
        for service, (_, manifest) in ALL_SERVICES.items():
            with self.subTest(service=service):
                _, _, mounts, volumes = parse_manifest(manifest)
                self.assertIsNotNone(mounts, f"{manifest} mounts no volumes")
                self.assertIn("- mountPath: /tmp", mounts)
                self.assertIn("name: tmp", mounts)
                # /tmp is backed by an emptyDir, not the image filesystem
                self.assertIsNotNone(volumes)
                self.assertIn("- emptyDir: {}", volumes)
                self.assertIn("name: tmp", volumes)

    def test_nothing_runs_as_root_or_privileged(self):
        for service, (_, manifest) in ALL_SERVICES.items():
            with self.subTest(service=service):
                text = (MANIFESTS / manifest).read_text()
                self.assertNotRegex(text, r"runAsUser:\s*0\b")
                self.assertNotIn("runAsNonRoot: false", text)
                self.assertNotIn("privileged: true", text)
                self.assertNotIn("readOnlyRootFilesystem: false", text)

    def test_every_service_is_covered(self):
        # a new service added to the kustomization must be added to this test
        listed = (MANIFESTS / "kustomization.yaml").read_text()
        app_manifests = set(re.findall(r"^\s*-\s*(\S+\.yaml)\s*$", listed, re.M)) - {
            "config.yaml", "accounts-db.yaml", "ledger-db.yaml"}
        covered = {manifest for _, manifest in ALL_SERVICES.values()}
        self.assertEqual(app_manifests, covered)


if __name__ == "__main__":
    unittest.main()
