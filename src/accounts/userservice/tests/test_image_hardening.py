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
The runtime image must not ship known-vulnerable OS packages (DEM-247): the
Debian security updates are applied when the image is built, perl-base (not
needed by Python) is removed and the build-only uv binary stays in the builder
stage. Only the standard library is used.
"""

import re
import unittest
from pathlib import Path

DOCKERFILE = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()


def stages(text):
    """The Dockerfile split into its build stages (text after each FROM)."""
    return re.split(r"^FROM\s", text, flags=re.M)[1:]


class ImageHardeningTest(unittest.TestCase):
    def setUp(self):
        self.runtime = stages(DOCKERFILE)[-1]

    def test_runtime_stage_applies_security_updates(self):
        self.assertRegex(self.runtime, r"apt-get update[\s\S]*apt-get -y [^\n]*upgrade")

    def test_runtime_stage_drops_perl_and_apt_lists(self):
        self.assertRegex(self.runtime, r"dpkg --purge [^\n]*perl-base")
        self.assertIn("/var/lib/apt/lists", self.runtime)

    def test_updates_are_applied_before_dropping_privileges(self):
        self.assertLess(self.runtime.index("apt-get"), self.runtime.index("USER 1000:1000"))

    def test_uv_is_only_in_the_builder_stage(self):
        with_uv = [s for s in stages(DOCKERFILE) if "astral-sh/uv" in s]
        self.assertEqual(len(with_uv), 1)
        self.assertIn("AS builder", with_uv[0])
        self.assertNotIn("astral-sh/uv", self.runtime)

    def test_base_image_is_still_pinned_by_digest(self):
        self.assertRegex(DOCKERFILE, r"(?m)^FROM python:\S+@sha256:[0-9a-f]{64} AS base$")


if __name__ == "__main__":
    unittest.main()
