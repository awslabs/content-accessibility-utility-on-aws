#!/usr/bin/env bash
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
# Regenerate the .drawio sources and export each to SVG (../img/*.svg).
#
# Requires the drawio desktop CLI on PATH as `drawio` (or set DRAWIO_BIN to the
# binary, e.g. an extracted AppImage's `drawio`). On a headless machine the
# script wraps the CLI in xvfb-run automatically.
#
# Usage:  ./export.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out_dir="$here/../img"
mkdir -p "$out_dir"

# 1. Generate the editable .drawio sources from the Python spec.
python3 "$here/gen_diagrams.py"

# 2. Locate the drawio binary.
drawio_bin="${DRAWIO_BIN:-drawio}"
if ! command -v "$drawio_bin" >/dev/null 2>&1 && [ ! -x "$drawio_bin" ]; then
  echo "error: drawio CLI not found. Install drawio-desktop or set DRAWIO_BIN." >&2
  exit 1
fi

# 3. Wrap in xvfb-run when there is no display (headless CI / server).
runner=()
if [ -z "${DISPLAY:-}" ] && command -v xvfb-run >/dev/null 2>&1; then
  runner=(xvfb-run -a)
fi

# 4. Export every source to SVG. --crop trims the page to the diagram bounds.
#    drawio (Electron) prints noisy dbus/GPU warnings on headless machines, so
#    per-file output is captured to a log; on failure we surface it and stop
#    rather than silently leaving a stale/missing SVG.
export TMPDIR="${TMPDIR:-/tmp}"
log="$(mktemp "${TMPDIR}/drawio-export.XXXXXX.log")"
# ${runner[@]+...} guards the empty-array expansion under `set -u` on bash 3.2
# (stock macOS), where a bare "${runner[@]}" would abort with "unbound variable".
shopt -s nullglob
for src in "$here"/*.drawio; do
  name="$(basename "$src" .drawio)"
  echo "exporting $name.svg"
  if ! ${runner[@]+"${runner[@]}"} "$drawio_bin" --no-sandbox --export \
      --format svg --crop --output "$out_dir/$name.svg" "$src" >"$log" 2>&1; then
    echo "error: drawio failed to export $name.svg" >&2
    cat "$log" >&2
    rm -f "$log"
    exit 1
  fi
done
rm -f "$log"

echo "done -> $out_dir"
