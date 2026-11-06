#!/usr/bin/env bash
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
# Tests for extract-release-notes.sh and the release step in publish.yml:
# the notes must come out byte-for-byte, and nothing in them may run.
#
#   .github/scripts/test-extract-release-notes.sh [CHANGELOG VERSION]
#
# With a CHANGELOG and VERSION it also checks that file's section.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
extract="$here/extract-release-notes.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

# 1. A section with backticks, $(...) and trailing blank line is copied exactly.
pwned="$work/pwned"
cat > "$work/CHANGELOG.md" <<EOF
# Changelog

## [2.0.0] - 2026-01-01

- Add \`--no-ai\` and \`chart\`; \`\$(touch $pwned)\` and \$(touch $pwned).

## [1.0.0] - 2025-01-01

- Old.
EOF
# shellcheck disable=SC2016 # the backticks and $(...) are literal on purpose
printf '## [2.0.0] - 2026-01-01\n\n- Add `--no-ai` and `chart`; `$(touch %s)` and $(touch %s).\n\n' \
  "$pwned" "$pwned" > "$work/expected.md"
"$extract" 2.0.0 "$work/CHANGELOG.md" > "$work/notes.md"
cmp "$work/expected.md" "$work/notes.md" || fail "section not byte-identical"

# 2. Missing version or file falls back to a plain title.
[ "$("$extract" 9.9.9 "$work/CHANGELOG.md")" = "Release v9.9.9" ] || fail "fallback (version)"
[ "$("$extract" 9.9.9 "$work/missing.md")" = "Release v9.9.9" ] || fail "fallback (file)"

# 3. The release step, run against a gh stub, passes the notes as a file and
#    never evaluates them.
mkdir -p "$work/bin" "$work/dist"
cat > "$work/bin/gh" <<'EOF'
#!/bin/sh
[ "$2" = view ] && exit 1   # release does not exist yet
printf '%s\n' "$@" > "$GH_ARGV"
EOF
chmod +x "$work/bin/gh"
touch "$work/dist/pkg-2.0.0-py3-none-any.whl"
cp "$work/notes.md" "$work/release-notes.md"
(
  cd "$work"
  export PATH="$work/bin:$PATH" GH_ARGV="$work/argv" TAG=v2.0.0 RUNNER_TEMP="$work"
  # Same script as the "Create or update GitHub Release" step.
  if gh release view "$TAG" > /dev/null 2>&1; then
    gh release upload "$TAG" dist/* --clobber
  else
    gh release create "$TAG" dist/* \
      --verify-tag \
      --title "Release $TAG" \
      --notes-file "$RUNNER_TEMP/release-notes.md"
  fi
)
[ ! -e "$pwned" ] || fail "notes were executed"
grep -qx -- '--notes-file' "$work/argv" || fail "gh was not given --notes-file"

# 4. Optional: a real changelog section, compared with a plain sed slice.
if [ $# -eq 2 ]; then
  sed -n "/^## \[$2\]/,\$p" "$1" | awk 'NR > 1 && /^## \[/ { exit } { print }' > "$work/real-expected.md"
  "$extract" "$2" "$1" > "$work/real.md"
  cmp "$work/real-expected.md" "$work/real.md" || fail "$1 section $2 not byte-identical"
  echo "ok: $1 [$2] $(wc -c < "$work/real.md") bytes, $(tr -cd '`' < "$work/real.md" | wc -c) backticks"
fi

echo "ok: release notes extraction and injection tests passed"
