---
title: Deployable Pipeline Guide
layout: default
parent: Get Started
nav_order: 3
description: "Deploy the managed, event-driven S3 → convert → audit → agent-remediate pipeline — no repo checkout required."
---

<!--
 Copyright 2025 Amazon.com, Inc. or its affiliates.
 SPDX-License-Identifier: Apache-2.0
-->

# Deployable Pipeline Guide

A complete, event-driven pipeline ships with the package: **upload a document to
S3 → convert (PDF) → audit → agent-remediate → accessible result written back to
S3**. It deploys from a plain `pip install` — no repository checkout required —
and runs the browser-backed [agent loop](rendered_agent_guide) on the managed
Amazon Bedrock **AgentCore** browser so you never bundle a Chromium binary.

<details markdown="block">
<summary><strong>On this page</strong></summary>

- [When to use the pipeline](#when-to-use-the-pipeline)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Option A — one-command deploy (recommended)](#option-a--one-command-deploy-recommended)
- [Option B — run the steps yourself](#option-b--run-the-steps-yourself)
- [Using the pipeline](#using-the-pipeline)
- [Prefix routing](#prefix-routing)
- [Outputs](#outputs)
- [IAM & permissions](#iam--permissions)
- [Updating & tearing down](#updating--tearing-down)
- [Troubleshooting](#troubleshooting)

</details>

## When to use the pipeline

Choose the managed pipeline when you want **hands-off processing at scale** —
documents are remediated automatically as they land in S3, with job tracking in
DynamoDB and no server to manage. If you instead want one-off/scripted runs, use
the [CLI](cli_guide); to embed processing in your own service, use the
[API](api_integration_guide).

### Why AgentCore

- **No browser in your artifact.** The heaviest, most fragile dependency (a
  ~150 MB browser + system libraries) is offloaded to the managed AgentCore
  Browser Tool, keeping images small and avoiding image-size limits.
- **Golden Path fit.** [Strands](https://strandsagents.com) is the framework
  AgentCore runs, and the agent already talks to Bedrock, so credentials, region,
  and IAM flow the same as the rest of the tool.
- **Longer sessions.** AgentCore Runtime supports multi-hour sessions (vs.
  Lambda's 15 minutes), which suits batch-remediating many documents.

## Architecture

![Managed pipeline: an upload to S3 (pdf/ or html/) triggers a Lambda that routes
pdf/*.pdf to convert-via-BDA and html/* straight to audit; audit feeds the agent
remediation running on AgentCore Runtime, which drives the AgentCore Browser Tool
and writes results to an accessible/ prefix in S3. The trigger and the agent both
write job records to DynamoDB.]({{ '/assets/img/managed-pipeline.svg' | relative_url }})

The deployment has two stacks that the tooling wires together for you:

1. **AgentCore Runtime** — runs `agentcore_app.py` (the agent loop) and drives the
   managed AgentCore browser. Built as an ARM64 image in the cloud (no local
   Docker needed).
2. **SAM stack** — the input S3 bucket, the trigger Lambda that routes uploads by
   prefix, and a DynamoDB table for job tracking. It's given the runtime ARN so
   the Lambda can invoke the agent.

## Prerequisites

```bash
# The agent extra (bundles the bedrock-agentcore SDK) plus the two deploy CLIs
pip install "content-accessibility-utility-on-aws[agent]"
pip install bedrock-agentcore-starter-toolkit aws-sam-cli
```

You also need:

- **AWS credentials** with permission to deploy CloudFormation/SAM, create the
  AgentCore runtime, and use the AgentCore Browser Tool, plus the Bedrock model
  and (for the PDF path) BDA permissions the tool already uses.
- **An AWS region** (via `--region`, `AWS_REGION`, or `AWS_DEFAULT_REGION`).
- **A globally-unique input bucket name.**
- **For the PDF path only:** a BDA bucket and a BDA project ARN. HTML/zip-only
  deployments can omit BDA. See the [CLI Guide prerequisites](cli_guide#prerequisites)
  for creating a BDA project.

## Option A — one-command deploy (recommended)

`deploy-pipeline` scaffolds the files and runs the whole multi-step deploy —
`agentcore configure` → `agentcore launch` → `sam deploy` — in order, prompting
for region, bucket, and (for the PDF path) BDA config, and capturing the runtime
ARN from the launch output so you never copy it between steps. Every
cloud-mutating step is confirmed first.

```bash
content-accessibility-utility-on-aws deploy-pipeline
```

Useful flags:

| Flag | Effect |
|---|---|
| `--dry-run` | Print the exact commands and exit without running anything |
| `--yes` / `-y` | Unattended (CI): skip confirmations **and** run `sam deploy` non-interactively |
| `--region` | AWS region (prompted if omitted) |
| `--input-bucket` | Input S3 bucket name — globally unique (prompted if omitted) |
| `--bda-bucket` | BDA S3 bucket (PDF path only; omit for HTML/zip only) |
| `--bda-project-arn` | BDA project ARN (PDF path) |
| `--runtime-name` | AgentCore runtime name (default `a11y_pipeline`) |
| `--force` | Overwrite existing scaffold files |
| `directory` | Directory to scaffold into (default `a11y-pipeline`) |

It shells out to the `agentcore` and `sam` CLIs (it does not reimplement them);
if either is missing it tells you and stops. If the runtime ARN can't be parsed
from the launch output it falls back to `.bedrock_agentcore.yaml` and finally
prompts, so a parse miss never blocks you.

Run `deploy-pipeline --dry-run` first to review every command that will execute
before anything touches your account.
{: .tip }

## Option B — run the steps yourself

Equivalent to Option A, if you'd rather run each step:

```bash
# 1. Write the deployment files (SAM template, runtime app, trigger Lambda).
content-accessibility-utility-on-aws init-pipeline ./a11y-pipeline
cd a11y-pipeline

# 2. Deploy the AgentCore Runtime (builds an ARM64 image in the cloud; no Docker).
#    For the PDF path, also pass BDA config as runtime env vars.
agentcore configure --entrypoint agentcore_app.py --name a11y_pipeline \
  --requirements-file requirements.txt --region <region>
agentcore launch --env BDA_S3_BUCKET=<bucket> --env BDA_PROJECT_ARN=<bda-project-arn>
#    -> note the runtime ARN it prints.

# 3. Deploy the S3 + Lambda + DynamoDB stack, wiring in that runtime ARN.
sam deploy --guided --parameter-overrides \
  AgentRuntimeArn=<runtime-arn> InputBucketName=<globally-unique-bucket>
```

`init-pipeline` also writes a `README.md` next to the files with these same
steps, the IAM the runtime role needs, and the BDA-project setup. Everything is
regenerable — re-run `init-pipeline --force` to refresh the files after a package
upgrade.

## Using the pipeline

Once deployed, just upload documents to the input bucket:

```bash
aws s3 cp report.pdf s3://<bucket>/pdf/report.pdf     # PDF  -> accessible/report/
aws s3 cp page.html  s3://<bucket>/html/page.html     # HTML -> accessible/page/
aws s3 cp site.zip   s3://<bucket>/html/site.zip      # zip  -> accessible/site/
```

## Prefix routing

The trigger Lambda routes by S3 prefix:

| Upload | Action |
|---|---|
| `pdf/*.pdf` | Convert → writes an HTML bundle under `html/<name>/` plus a `manifest.json` that auto-triggers audit |
| `html/<name>.html` | Audit + remediate |
| `html/<name>.zip` | Audit + remediate (a bundle of HTML + images/CSS/JS) |
| `html/<name>/manifest.json` | Audit + remediate a multi-file bundle |

A single HTML file with **external** images degrades to placeholder alt text
(the image bytes aren't available to describe). Upload a **zip** bundling the
HTML with its images/CSS/JS to get full multimodal alt text.
{: .note }

## Outputs

Each run writes the following to `accessible/<name>/`:

| File | Contents |
|---|---|
| `<name>.remediated.html` (+ assets) | The fixed document |
| `accessibility_audit_before.json` | Findings **before** remediation |
| `accessibility_audit.json` | Findings **after** remediation (the residual) |
| `remediation_gap.json` | `issues_before` / `issues_after` / `issues_resolved` and residual-by-criterion — measure exactly what was fixed |

The same before/after/resolved counts are recorded on the DynamoDB job record, so
you can track progress and measure remediation coverage without opening the files.

## IAM & permissions

The AgentCore runtime role needs:

- **Bedrock** model invocation (for remediation and, on the PDF path, BDA).
- **AgentCore Browser Tool** usage.
- **S3** read on the input bucket and write to the `accessible/` prefix.
- **DynamoDB** write to the job-tracking table.

The exact policy is written into the `README.md` that `init-pipeline` generates
next to the scaffold, tailored to your bucket and table names. Follow the
principle of least privilege and scope the S3/DynamoDB statements to the specific
resources the SAM stack creates.

## Updating & tearing down

**Update** after a package upgrade — regenerate the scaffold and redeploy:

```bash
content-accessibility-utility-on-aws init-pipeline ./a11y-pipeline --force
cd a11y-pipeline
agentcore launch   # rebuild the runtime image
sam deploy         # redeploy the stack
```

**Tear down** — delete the SAM stack and the AgentCore runtime:

```bash
sam delete
agentcore destroy   # or delete the runtime from the console
```

Deleting resources is irreversible. Confirm you're in the intended
(non-production) account and region, and that the input/output S3 data is no
longer needed, before running `sam delete`. Emptying the bucket first is
required if it still contains objects.
{: .warning }

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `deploy-pipeline` stops: "agentcore/sam not found" | Install the deploy CLIs: `pip install bedrock-agentcore-starter-toolkit aws-sam-cli`. |
| Runtime ARN not captured after `launch` | The tool falls back to `.bedrock_agentcore.yaml`, then prompts — paste the ARN from the launch output. |
| Uploads not processed | Confirm the object is under `pdf/` or `html/`, and check the trigger Lambda's CloudWatch logs. |
| PDF conversion fails | The runtime needs `BDA_S3_BUCKET` + `BDA_PROJECT_ARN` env vars (set at `agentcore launch`) and BDA permissions. |
| External images get placeholder alt text | Upload a **zip** bundling the HTML with its images so the agent can see the bytes. |
| AgentCore browser session errors | Verify the runtime role can use the AgentCore Browser Tool and the region supports it. |

The hosted path has been validated end-to-end against live AgentCore sessions in
a staging account — still validate in your own non-production account before
relying on it. See the [Rendered Audit & Agent Guide](rendered_agent_guide#deploying-in-aws-agentcore)
for the deeper architecture, the verify-before-commit guarantee, and the
configuration reference.
