#!/usr/bin/env bash
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
# Build the local package wheel that the AgentCore runtime installs.
#
# The runtime installs the browser/agent layer from a locally built wheel (see
# requirements.txt) rather than PyPI, because that layer is not yet published.
# The wheel is a build artifact and is intentionally NOT committed (it is
# gitignored), so regenerate it here before deploying:
#
#     deployment/build_wheel.sh
#     # then: agentcore launch  (or the documented deploy steps)
#
# Safe to re-run; it overwrites the existing wheel in deployment/.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
deploy_dir="$repo_root/deployment"

echo "Building wheel from $repo_root ..."
python3 -m build --wheel --outdir "$deploy_dir/dist" "$repo_root"

wheel="$(ls -t "$deploy_dir"/dist/content_accessibility_utility_on_aws-*.whl | head -1)"
cp "$wheel" "$deploy_dir/$(basename "$wheel")"
echo "Wheel ready: deployment/$(basename "$wheel")"
