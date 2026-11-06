#!/usr/bin/env bash
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
# Print the CHANGELOG.md section for one version to stdout.
#
#   extract-release-notes.sh VERSION [CHANGELOG]
#
# The section runs from "## [VERSION]" up to, not including, the next
# "## [" heading (or end of file). The text is printed as data only: it is
# never evaluated by a shell, so backticks and $(...) in the notes are safe.
# Prints "Release vVERSION" when the file or the section is missing.
set -euo pipefail

version="${1:?usage: extract-release-notes.sh VERSION [CHANGELOG]}"
changelog="${2:-CHANGELOG.md}"

notes=""
if [ -f "$changelog" ]; then
  notes="$(awk -v ver="$version" '
    BEGIN { found = 0 }
    /^## \[/ {
      if (found) exit
      if (index($0, "[" ver "]") > 0) found = 1
    }
    found { print }
  ' "$changelog"; printf x)"
  notes="${notes%x}"  # keep trailing newlines byte-for-byte
fi

if [ -z "$notes" ]; then
  printf 'Release v%s\n' "$version"
else
  printf '%s' "$notes"
fi
