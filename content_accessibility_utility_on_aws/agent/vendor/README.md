# Vendored axe-core

| | |
|---|---|
| **Package** | [axe-core](https://github.com/dequelabs/axe-core) |
| **Version** | `4.10.2` |
| **File** | `axe.min.js` |
| **SHA-256** | `b511cd9dec01c76f4b2ad1723b66b6db37d4c2eb4ed199076e1829d9ee7b75e3` |
| **Source** | https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js |
| **License** | MPL-2.0 (Mozilla Public License 2.0) — see the license header in `axe.min.js` |

`axe.min.js` is injected into each rendered page by the browser probe
(`agent/browser_probe.py`) to run the accessibility rule set.

## Why this is committed to the repo (not fetched at install/runtime)

Vendoring a **pinned** copy — rather than downloading axe-core on install or on
first use — is deliberate:

1. **Hermetic at runtime.** The audit must not make a network request in the
   request path. The hosted path renders in the **managed Amazon Bedrock
   AgentCore browser**, and real deployments are often air-gapped / VPC-only /
   egress-restricted; a CDN fetch mid-audit could hang or fail. The rule engine
   must already be present when the audit runs.
2. **Deterministic.** axe-core's rules change between versions. A floating
   version would silently change which WCAG violations are reported from one run
   to the next, undermining the agent's "detect → fix → **verify**" guarantee
   (the verify step re-runs axe and must measure against the same rules).
3. **Auditable supply chain.** A pinned, in-repo, checksum-verified file cannot
   be swapped underneath us, unlike a CDN fetch or a floating dependency.

Alternatives were considered and rejected: fetch-on-first-use and
fetch-at-install both reintroduce a network dependency (breaking #1) and are
fragile in locked-down build/deploy sandboxes; the `axe-core-python` PyPI
wrapper is a single-release third party (worse for #2/#3 than a first-party
pin); an npm dependency imposes a Node toolchain on a pip-installed library.

## Integrity check

`browser_probe._load_axe()` computes the SHA-256 of this file on load and
refuses to run if it does not match `_AXE_SHA256` in `agent/browser_probe.py`.
This catches truncation, tampering, an accidental version swap, or a **Git LFS
pointer stub** packaged in place of the real bytes — any of which would
otherwise silently run a different (or no) rule set. **Do not** track this file
with Git LFS: it ships as package data inside the wheel, and a build from a tree
without `git lfs pull` would package the pointer text, which the load-time check
would then (correctly) reject.

## Updating axe-core

Use the script — it downloads the pinned version and prints the new SHA-256:

```bash
agent/vendor/update_axe.sh 4.11.0     # or omit the arg to re-fetch the current version
```

Then update **both** pins so the load-time integrity check passes (the script
prints the exact values):

1. `agent/browser_probe.py` — `_AXE_VERSION` and `_AXE_SHA256`
2. this README — the **Version** and **SHA-256** rows above

Run the rendered tests (`pytest -m rendered`) after updating, since a new
axe-core version can change the set of reported violations.
