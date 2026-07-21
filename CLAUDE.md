<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Guidance for AI coding agents

Start here, then read the linked docs — this file is an index, not a manual.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — build/test commands, the PR workflow,
  and the **documentation requirement** (docs must be updated in the same PR;
  see its [Documentation](CONTRIBUTING.md#documentation) section for the
  change-→-page map, the GitHub Pages site, and the diagram workflow).
- **[TESTING_PLAN.md](TESTING_PLAN.md)** — the tiered test strategy.
- **[README.md](README.md)** — what the project is and the three ways to use it.
- **User docs** — [`docs/`](docs/), published as a GitHub Pages site; the guides
  are the authoritative reference for the CLI, API, and pipeline.

## Rules for agents

1. **Keep docs in lockstep with code.** Any user-visible change must update the
   matching page(s) in the same change — follow the map in
   [CONTRIBUTING.md § Documentation](CONTRIBUTING.md#documentation). This is a
   requirement, not a follow-up.
2. Before committing, the default `pytest` run (see CONTRIBUTING.md) must pass.
3. Match the conventions already in the tree: the Apache-2.0 header on new
   files, inclusive language, and the style of surrounding code.

Other agents (Codex, etc.) are routed here via [AGENTS.md](AGENTS.md).
