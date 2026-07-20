# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser-free tests for the vendored axe-core integrity guard.

`_load_axe` verifies the committed axe.min.js matches the pinned SHA-256, so a
truncated/tampered/version-mismatched copy — or a Git LFS pointer stub packaged
in place of the real bytes — fails loudly instead of silently running a
different rule set. These need no browser (they call the static loader).
"""

import hashlib

import pytest

from content_accessibility_utility_on_aws.agent import browser_probe as bp
from content_accessibility_utility_on_aws.agent.browser_probe import (
    BrowserUnavailableError,
)


def test_vendored_axe_matches_pinned_hash():
    # The committed file must actually match the pin recorded in the module and
    # the vendor README (guards against an update that bumps the file but not
    # the hash, or vice versa).
    with open(bp._AXE_JS_PATH, "rb") as fh:
        actual = hashlib.sha256(fh.read()).hexdigest()
    assert actual == bp._AXE_SHA256


def test_load_axe_returns_script_when_hash_matches():
    js = bp._PlaywrightProbeBase._load_axe()
    assert "axe" in js.lower()
    assert len(js) > 100_000  # a real axe build, not a stub


def test_load_axe_rejects_mismatched_file(tmp_path, monkeypatch):
    # Simulate a swapped/tampered/LFS-pointer file: content whose hash != pin.
    fake = tmp_path / "axe.min.js"
    fake.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:deadbeef\n")
    monkeypatch.setattr(bp, "_AXE_JS_PATH", str(fake))
    with pytest.raises(BrowserUnavailableError, match="does not match the pinned"):
        bp._PlaywrightProbeBase._load_axe()


def test_load_axe_missing_file_is_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(bp, "_AXE_JS_PATH", str(tmp_path / "nope.js"))
    with pytest.raises(BrowserUnavailableError, match="not found"):
        bp._PlaywrightProbeBase._load_axe()
