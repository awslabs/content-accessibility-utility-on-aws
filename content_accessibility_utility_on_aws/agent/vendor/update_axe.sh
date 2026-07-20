#!/usr/bin/env bash
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
# Re-vendor axe-core reproducibly and verifiably.
#
# axe-core is vendored (committed) rather than fetched at runtime so that
# rendered audits are hermetic (no network in the request path — the hosted
# path renders in a managed AgentCore browser that may have no egress) and
# deterministic (a floating version would silently change which WCAG rules
# run). This script is the ONLY supported way to bump it: it downloads the
# pinned version, prints the SHA-256, and updates the file in place. After
# running it you MUST update the two pins that guard the file:
#   - _AXE_VERSION / _AXE_SHA256 in agent/browser_probe.py
#   - the version + SHA-256 line in this directory's README.md
# browser_probe._load_axe() verifies the file against _AXE_SHA256 on load, so
# forgetting to update the hash fails loudly rather than shipping a mismatch.
#
# Usage:
#   agent/vendor/update_axe.sh 4.10.2          # pin a specific version (recommended)
#   agent/vendor/update_axe.sh                 # re-fetch the current DEFAULT_VERSION
set -euo pipefail

DEFAULT_VERSION="4.10.2"
VERSION="${1:-$DEFAULT_VERSION}"
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$DIR/axe.min.js"
URL="https://cdn.jsdelivr.net/npm/axe-core@${VERSION}/axe.min.js"

echo "Downloading axe-core ${VERSION} from ${URL}"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsSL "$URL" -o "$tmp"

# Sanity: axe.min.js should be a few hundred KB of JS, not an error page.
bytes="$(wc -c < "$tmp")"
if [ "$bytes" -lt 100000 ]; then
  echo "ERROR: downloaded file is only ${bytes} bytes — not a valid axe build." >&2
  exit 1
fi

sha="$(sha256sum "$tmp" | cut -d' ' -f1)"
mv "$tmp" "$DEST"
trap - EXIT

echo
echo "Vendored: $DEST (${bytes} bytes)"
echo "Version : ${VERSION}"
echo "SHA-256 : ${sha}"
echo
echo "Now update the pins so the load-time check passes:"
echo "  1. agent/browser_probe.py:  _AXE_VERSION = \"${VERSION}\""
echo "                              _AXE_SHA256  = \"${sha}\""
echo "  2. agent/vendor/README.md:  version + SHA-256 line"
