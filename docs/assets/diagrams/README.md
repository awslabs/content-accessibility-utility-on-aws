<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->
# Documentation diagrams

The docs use SVG diagrams instead of Mermaid (GitHub Pages does not render
Mermaid without a plugin, and PyPI renders neither). Each diagram is authored in
[drawio](https://www.drawio.com/) and exported to SVG.

## Files

- `gen_diagrams.py` — generates the editable `*.drawio` sources from a compact
  node/edge spec, so the diagrams are reviewable as data and share one palette.
  Edit the specs here, or open the `.drawio` files directly in the drawio app.
- `*.drawio` — the editable diagram sources (open these in drawio to tweak).
- `export.sh` — regenerates the sources and exports each to `../img/*.svg`.
- `../img/*.svg` — the exported SVGs referenced by the Markdown pages (committed;
  no build step runs at deploy time).

## Regenerating

You need the [drawio desktop](https://github.com/jgraph/drawio-desktop) CLI on
`PATH` as `drawio` (or point `DRAWIO_BIN` at the binary — e.g. an extracted
AppImage's `drawio`). On a headless machine the script wraps the CLI in
`xvfb-run` automatically.

```bash
./export.sh
```

Then update the `![alt](...)/img/<name>.svg` reference in the relevant Markdown
page if you added or renamed a diagram. Keep the alt text descriptive — it is the
accessible description of the diagram, and this project is about accessibility.

> **Note:** avoid literal `<` / `>` characters in Markdown image alt text —
> kramdown treats them as HTML tags and breaks the `![...](...)` syntax. Spell
> out placeholders (e.g. "an accessible/ prefix" rather than `accessible/<name>/`).
