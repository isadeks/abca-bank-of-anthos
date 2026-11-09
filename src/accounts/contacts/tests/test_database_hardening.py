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

"""Checks that the accounts-db and ledger-db images and manifests run Postgres as non-root.

The manifests are read as text (no YAML dependency): each check looks at the lines
nested under a given key, found by indentation.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

DATABASES = {
    'accounts-db': {
        'manifest': REPO / 'kubernetes-manifests' / 'accounts-db.yaml',
        'dockerfile': REPO / 'src' / 'accounts' / 'accounts-db' / 'Dockerfile',
        'initdb': REPO / 'src' / 'accounts' / 'accounts-db' / 'initdb',
    },
    'ledger-db': {
        'manifest': REPO / 'kubernetes-manifests' / 'ledger-db.yaml',
        'dockerfile': REPO / 'src' / 'ledger' / 'ledger-db' / 'Dockerfile',
        'initdb': REPO / 'src' / 'ledger' / 'ledger-db' / 'initdb',
    },
}

POSTGRES_UID = '70'


def indent_of(line):
    return len(line) - len(line.lstrip(' '))


def statefulset(manifest):
    """The lines of the StatefulSet document, comments removed."""
    for doc in manifest.read_text().split('\n---\n'):
        if re.search(r'^kind: StatefulSet$', doc, re.M):
            return [l for l in doc.splitlines()
                    if l.strip() and not l.strip().startswith('#')]
    raise AssertionError(f'no StatefulSet in {manifest}')


def block(lines, key, start=0):
    """Lines nested under the first `key:` at or after `start`, as (children, index)."""
    for i in range(start, len(lines)):
        stripped = lines[i].lstrip(' -')
        if stripped.startswith(key + ':'):
            base = indent_of(lines[i].replace('- ', '  ', 1)) if lines[i].lstrip().startswith('- ') \
                else indent_of(lines[i])
            children = []
            for line in lines[i + 1:]:
                if indent_of(line) <= base and not line.lstrip().startswith('- ') \
                        or indent_of(line) < base:
                    break
                children.append(line)
            return children, i
    raise AssertionError(f'{key} not found')


def scalars(children):
    """`key: value` pairs of a block (list items flattened)."""
    out = {}
    for line in children:
        m = re.match(r'^\s*(?:- )?([\w.-]+): (.+)$', line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


class DatabaseManifestTest(unittest.TestCase):

    def setUp(self):
        self.sets = {n: statefulset(d['manifest']) for n, d in DATABASES.items()}

    def test_pod_runs_as_postgres_with_writable_fsgroup(self):
        for name, lines in self.sets.items():
            with self.subTest(db=name):
                pod, _ = block(lines, 'spec', next(
                    i for i, l in enumerate(lines) if l.startswith('  template:')))
                sec, _ = block(pod, 'securityContext')
                values = scalars(sec)
                self.assertEqual(values['runAsNonRoot'], 'true')
                self.assertEqual(values['runAsUser'], POSTGRES_UID)
                self.assertEqual(values['runAsGroup'], POSTGRES_UID)
                self.assertEqual(values['fsGroup'], POSTGRES_UID)

    def test_container_is_locked_down(self):
        for name, lines in self.sets.items():
            with self.subTest(db=name):
                sec, _ = block(lines, 'securityContext', next(
                    i for i, l in enumerate(lines) if l.startswith('      containers:')))
                values = scalars(sec)
                self.assertEqual(values['allowPrivilegeEscalation'], 'false')
                self.assertEqual(values['readOnlyRootFilesystem'], 'true')
                self.assertEqual(values['runAsNonRoot'], 'true')
                self.assertEqual(values['runAsUser'], POSTGRES_UID)
                caps, _ = block(sec, 'capabilities')
                drop, _ = block(caps, 'drop')
                self.assertEqual([l.strip() for l in drop], ['- ALL'])
                self.assertNotIn('add', '\n'.join(caps))
                self.assertNotIn('privileged: true', '\n'.join(sec))

    def test_only_postgres_paths_are_writable(self):
        for name, lines in self.sets.items():
            with self.subTest(db=name):
                mounts, _ = block(lines, 'volumeMounts')
                paths = sorted(re.findall(r'mountPath: (\S+)', '\n'.join(mounts)))
                self.assertEqual(paths, ['/tmp', '/var/lib/postgresql/data', '/var/run/postgresql'])
                self.assertNotIn('readOnly: false', '\n'.join(mounts))
                # Each mount is backed by a volume.
                volumes, _ = block(lines, 'volumes')
                mount_names = re.findall(r'name: (\S+)', '\n'.join(mounts))
                for volume in mount_names:
                    self.assertIn(f'name: {volume}', '\n'.join(volumes))

    def test_data_directory_is_not_a_root_owned_subpath(self):
        for name, lines in self.sets.items():
            with self.subTest(db=name):
                text = '\n'.join(lines)
                self.assertNotIn('subPath', text)
                self.assertIn('value: /var/lib/postgresql/data/pgdata', text)
                self.assertIn('name: PGDATA', text)


class DatabaseDockerfileTest(unittest.TestCase):

    def instructions(self, name):
        text = DATABASES[name]['dockerfile'].read_text()
        return [l.strip() for l in text.splitlines()
                if l.strip() and not l.strip().startswith('#')]

    def test_final_user_is_postgres(self):
        for name in DATABASES:
            with self.subTest(db=name):
                users = [l for l in self.instructions(name) if l.startswith('USER ')]
                self.assertTrue(users, 'no USER instruction')
                self.assertRegex(users[-1], rf'^USER {POSTGRES_UID}(:{POSTGRES_UID})?$')
                # Nothing after the final USER may need root.
                after = self.instructions(name)[self.instructions(name).index(users[-1]) + 1:]
                self.assertEqual([l for l in after if l.startswith(('RUN ', 'ADD '))], [])

    def test_init_scripts_are_installed_readable_and_executable(self):
        for name, d in DATABASES.items():
            with self.subTest(db=name):
                lines = self.instructions(name)
                text = '\n'.join(lines)
                for script in sorted(p.name for p in d['initdb'].iterdir()
                                     if p.suffix in ('.sh', '.sql')):
                    if script.endswith('.sql') and script.startswith('1'):
                        continue  # not copied into the image
                    self.assertIn(script, text, f'{script} not copied into the image')
                    self.assertRegex(text, rf'chmod 755 [^\n]*{re.escape(script)}')
                # chmod runs as root, before the switch to postgres.
                chmod = next(i for i, l in enumerate(lines) if 'chmod' in l)
                user = max(i for i, l in enumerate(lines) if l.startswith('USER '))
                self.assertLess(chmod, user)

    def test_ledger_db_installs_coreutils_as_root(self):
        lines = self.instructions('ledger-db')
        apk = next(i for i, l in enumerate(lines) if 'apk add' in l and 'coreutils' in l)
        user = max(i for i, l in enumerate(lines) if l.startswith('USER '))
        self.assertLess(apk, user)

    def test_init_scripts_are_executable_files(self):
        for name, d in DATABASES.items():
            for script in d['initdb'].glob('*.sh'):
                with self.subTest(script=str(script.relative_to(REPO))):
                    self.assertTrue(script.read_text().startswith('#!/bin/bash'))


if __name__ == '__main__':
    unittest.main()
