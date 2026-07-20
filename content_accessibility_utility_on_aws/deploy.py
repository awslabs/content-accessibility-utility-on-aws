# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Interactive orchestrator for the managed AgentCore pipeline deployment.

``init-pipeline`` writes the deployment files; this module drives the multi-step
deploy those files require — scaffold → ``agentcore configure`` → ``agentcore
launch`` → ``sam deploy`` — so the user does not copy-paste commands or the
runtime ARN between steps.

Design notes:
- It is a thin **orchestrator**: it shells out to the ``agentcore`` and ``sam``
  CLIs rather than reimplementing them (the ARM64 image build + ECR push that
  ``agentcore launch`` performs is exactly what we do not want to own). It never
  makes AWS mutations itself except through those tools.
- Every cloud-mutating step is **confirmed** ("proceed? [y/N]") unless the caller
  passes ``assume_yes`` (``--yes``), and ``dry_run`` prints the plan without
  running anything. This command creates billable, outward-facing resources.
- The one fragile parse — the runtime ARN emitted by ``agentcore launch`` — has
  a deterministic fallback: the ARN is also written to
  ``.bedrock_agentcore.yaml`` (``agent_arn``), which we read if the stdout parse
  fails, and we prompt as a last resort.

The pure, side-effect-free helpers (``parse_runtime_arn``, ``read_arn_from_yaml``,
``build_plan``) are separated from the subprocess-running functions so they can
be unit-tested offline.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess  # nosec B404 - orchestrating agentcore/sam CLIs is the point
from dataclasses import dataclass
from typing import Callable, List, Optional

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)

# ARN of an AgentCore runtime, as printed by `agentcore launch` and stored in
# .bedrock_agentcore.yaml. Anchored to the runtime resource so we don't grab a
# different agentcore ARN that may also appear in the output.
_RUNTIME_ARN_RE = re.compile(
    r"arn:aws[a-z0-9-]*:bedrock-agentcore:[a-z0-9-]+:\d{12}:runtime/[A-Za-z0-9_-]+"
)

# Default runtime/agent name (matches the docs and the SAM stack expectations).
DEFAULT_RUNTIME_NAME = "a11y_pipeline"
DEFAULT_DIRECTORY = "a11y-pipeline"


class DeployError(RuntimeError):
    """A deployment step failed or a prerequisite is missing."""


# ---------------------------------------------------------------------------
# Pure helpers (no side effects) — unit-tested offline
# ---------------------------------------------------------------------------

def parse_runtime_arn(text: str) -> Optional[str]:
    """Extract the AgentCore runtime ARN from ``agentcore launch`` output.

    Returns the last match (the final "Deployment completed … Agent: <arn>"
    line, when both a create and a completion line are present), or None.
    """
    matches = _RUNTIME_ARN_RE.findall(text or "")
    return matches[-1] if matches else None


def read_arn_from_yaml(config_path: str) -> Optional[str]:
    """Read ``agent_arn`` from a ``.bedrock_agentcore.yaml`` file, or None.

    A deterministic fallback for when the stdout parse fails: the toolkit writes
    the runtime ARN here after a successful launch. Parsed with a line scan so
    this module has no YAML dependency.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("agent_arn:"):
                    value = stripped.split(":", 1)[1].strip().strip("'\"")
                    return value or None
    except OSError:
        return None
    return None


@dataclass
class DeployConfig:
    """Everything the deploy needs; prompted for or passed via flags."""

    directory: str = DEFAULT_DIRECTORY
    region: str = ""
    runtime_name: str = DEFAULT_RUNTIME_NAME
    input_bucket: str = ""
    bda_bucket: str = ""            # optional; only needed for the PDF path
    bda_project_arn: str = ""       # optional; only needed for the PDF path
    force: bool = False


@dataclass
class Step:
    """One planned command in the deploy sequence."""

    title: str
    argv: List[str]
    cwd: Optional[str] = None
    # Whether to capture this step's output (so a return value can be parsed)
    # vs. let it inherit the terminal. Interactive steps (agentcore configure,
    # sam deploy --guided) MUST NOT be captured or their prompts are buffered
    # invisibly and the child blocks on stdin the user cannot see. Only
    # ``agentcore launch`` is captured, to parse the runtime ARN from its output.
    capture: bool = False


def build_plan(cfg: DeployConfig) -> List[Step]:
    """Build the ordered command plan from a config (no execution).

    Kept pure so a --dry-run and the tests can inspect the exact commands
    without running anything. BDA env vars are attached to ``agentcore launch``
    only when provided (the PDF path); an HTML/zip-only deploy omits them.
    """
    workdir = os.path.abspath(cfg.directory)
    launch_argv = ["agentcore", "launch"]
    for key, val in (
        ("BDA_S3_BUCKET", cfg.bda_bucket),
        ("BDA_PROJECT_ARN", cfg.bda_project_arn),
    ):
        if val:
            launch_argv += ["--env", f"{key}={val}"]

    return [
        Step(
            title="Configure the AgentCore runtime",
            argv=[
                "agentcore", "configure",
                "--entrypoint", "agentcore_app.py",
                "--name", cfg.runtime_name,
                "--requirements-file", "requirements.txt",
                "--region", cfg.region,
            ],
            cwd=workdir,
            capture=False,  # configure prompts interactively for role/ECR/etc.
        ),
        Step(
            title="Launch the AgentCore runtime (builds an ARM64 image in the cloud)",
            argv=launch_argv,
            cwd=workdir,
            capture=True,  # non-interactive; captured so we can parse the ARN
        ),
        # The sam deploy step's AgentRuntimeArn is filled in after launch, so it
        # is built dynamically in run_deploy, not here.
    ]


def sam_deploy_argv(cfg: DeployConfig, runtime_arn: str, assume_yes: bool) -> List[str]:
    """Build the ``sam deploy`` argv.

    Interactive by default (``--guided`` walks the user through stack name,
    region, and change-set confirmation). With ``assume_yes`` (``--yes`` / CI)
    ``--guided`` would still prompt, so use the non-interactive flags instead:
    an explicit stack name, ``--resolve-s3`` for the deployment bucket, and the
    IAM capability the template's Lambda role requires. CloudFormation stack
    names disallow ``_``, so the runtime name is hyphenated.
    """
    argv = ["sam", "deploy"]
    if assume_yes:
        argv += [
            "--stack-name", cfg.runtime_name.replace("_", "-"),
            "--resolve-s3",
            "--capabilities", "CAPABILITY_IAM",
            "--no-confirm-changeset",
            "--no-fail-on-empty-changeset",
        ]
        if cfg.region:
            argv += ["--region", cfg.region]
    else:
        argv += ["--guided"]
    argv += [
        "--parameter-overrides",
        f"AgentRuntimeArn={runtime_arn}",
        f"InputBucketName={cfg.input_bucket}",
    ]
    return argv


def format_plan(cfg: DeployConfig, assume_yes: bool = False) -> str:
    """Human-readable dry-run plan (commands, in order)."""
    lines = [
        "Deployment plan (4 steps):",
        f"  1. scaffold files into {os.path.abspath(cfg.directory)}",
    ]
    for i, step in enumerate(build_plan(cfg), start=2):
        lines.append(f"  {i}. {step.title}")
        lines.append("       " + " ".join(step.argv))
    lines.append("  4. Deploy the SAM stack (uses the runtime ARN from launch)")
    lines.append(
        "       " + " ".join(sam_deploy_argv(cfg, "<from-launch>", assume_yes))
    )
    if not (cfg.bda_bucket and cfg.bda_project_arn):
        lines.append(
            "  note: no BDA config supplied — the PDF path will be unavailable; "
            "HTML/zip inputs work. Re-run with --bda-bucket/--bda-project-arn to enable PDF."
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Side-effecting steps
# ---------------------------------------------------------------------------

def check_prerequisites(which: Callable[[str], Optional[str]] = shutil.which) -> List[str]:
    """Return a list of missing prerequisite CLIs (empty if all present)."""
    missing = []
    for tool in ("agentcore", "sam"):
        if which(tool) is None:
            missing.append(tool)
    return missing


def _confirm(prompt: str, assume_yes: bool, input_fn: Callable[[str], str]) -> bool:
    if assume_yes:
        return True
    answer = input_fn(f"{prompt} [y/N]: ").strip().lower()
    return answer in ("y", "yes")


MISSING_TOOLS_HELP = (
    "Install them first:\n"
    "  pip install bedrock-agentcore-starter-toolkit aws-sam-cli"
)


def _run(
    step_argv: List[str],
    cwd: Optional[str],
    extra_env: Optional[dict] = None,
    capture: bool = False,
) -> str:
    """Run a command; raise DeployError on non-zero exit.

    ``capture=True`` pipes stdout (returned to the caller so it can be parsed,
    e.g. for the runtime ARN) and prints it after the process exits.
    ``capture=False`` lets the child inherit this process's stdin/stdout/stderr
    so INTERACTIVE tools (agentcore configure, sam deploy --guided) can prompt
    and read the user's answers live — capturing them would buffer the prompts
    invisibly and block on stdin. Returns "" when not capturing.
    """
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    logger.info("Running: %s (cwd=%s)", " ".join(step_argv), cwd or ".")
    if capture:
        proc = subprocess.run(  # nosec B603 - argv list, no shell; trusted CLIs
            step_argv, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        output = proc.stdout or ""
        print(output, end="" if output.endswith("\n") else "\n")
    else:
        # Inherit the terminal so the child's prompts stream to the user.
        proc = subprocess.run(step_argv, cwd=cwd, env=env)  # nosec B603
        output = ""
    if proc.returncode != 0:
        raise DeployError(
            f"Command failed (exit {proc.returncode}): {' '.join(step_argv)}"
        )
    return output


def _prompt(label: str, default: str, input_fn: Callable[[str], str]) -> str:
    suffix = f" [{default}]" if default else ""
    value = input_fn(f"{label}{suffix}: ").strip()
    return value or default


def prompt_for_config(
    cfg: DeployConfig, input_fn: Callable[[str], str] = input
) -> DeployConfig:
    """Fill any unset config fields interactively (flags win over prompts)."""
    cfg.directory = cfg.directory or _prompt("Deployment directory", DEFAULT_DIRECTORY, input_fn)
    cfg.region = cfg.region or _prompt(
        "AWS region", os.environ.get("AWS_REGION", ""), input_fn
    )
    cfg.runtime_name = cfg.runtime_name or _prompt(
        "Runtime name", DEFAULT_RUNTIME_NAME, input_fn
    )
    cfg.input_bucket = cfg.input_bucket or _prompt(
        "Input S3 bucket name (globally unique)", "", input_fn
    )
    # BDA is only needed for the PDF path; leave blank to skip.
    if not cfg.bda_bucket:
        cfg.bda_bucket = _prompt(
            "BDA S3 bucket (blank to skip PDF support)", "", input_fn
        )
    if cfg.bda_bucket and not cfg.bda_project_arn:
        cfg.bda_project_arn = _prompt("BDA project ARN", "", input_fn)
    if not cfg.region:
        raise DeployError("An AWS region is required.")
    if not cfg.input_bucket:
        raise DeployError("An input bucket name is required.")
    return cfg


def run_deploy(
    cfg: DeployConfig,
    scaffold: Callable[[str, bool], None],
    *,
    assume_yes: bool = False,
    dry_run: bool = False,
    input_fn: Callable[[str], str] = input,
    runner: Callable[..., str] = _run,
) -> int:
    """Orchestrate the full deploy. Returns a process exit code.

    ``scaffold(directory, force)`` writes the deployment files (injected so the
    CLI reuses ``init-pipeline``'s copier and tests can stub it). ``runner`` runs
    a command and returns its output (injected for offline tests).
    """
    if dry_run:
        print(format_plan(cfg, assume_yes))
        return 0

    workdir = os.path.abspath(cfg.directory)

    # 1. Scaffold the deployment files.
    print(f"\n== Step 1/4: scaffold deployment files into {workdir} ==")
    scaffold(cfg.directory, cfg.force)

    # 2 & 3. agentcore configure + launch.
    steps = build_plan(cfg)
    launch_output = ""
    for idx, step in enumerate(steps):
        print(f"\n== Step {idx + 2}/4: {step.title} ==")
        print("  " + " ".join(step.argv))
        if not _confirm("Proceed?", assume_yes, input_fn):
            print("Aborted by user.")
            return 1
        out = runner(
            step.argv,
            step.cwd,
            {"AWS_REGION": cfg.region} if cfg.region else None,
            step.capture,
        )
        if step.argv[:2] == ["agentcore", "launch"]:
            launch_output = out

    # Capture the runtime ARN: parse stdout, fall back to the toolkit's yaml,
    # then prompt as a last resort so a parse miss never blocks the deploy.
    runtime_arn = parse_runtime_arn(launch_output)
    if not runtime_arn:
        runtime_arn = read_arn_from_yaml(
            os.path.join(workdir, ".bedrock_agentcore.yaml")
        )
    if not runtime_arn:
        runtime_arn = input_fn(
            "Could not detect the runtime ARN automatically. Paste it: "
        ).strip()
    if not runtime_arn:
        raise DeployError("No runtime ARN available; cannot deploy the SAM stack.")
    print(f"\nRuntime ARN: {runtime_arn}")

    # 4. sam deploy, wiring in the captured ARN + bucket. Interactive (--guided)
    # unless --yes, so it must run uncaptured to prompt the user.
    sam_argv = sam_deploy_argv(cfg, runtime_arn, assume_yes)
    print("\n== Step 4/4: deploy the SAM stack ==")
    print("  " + " ".join(sam_argv))
    if not _confirm("Proceed?", assume_yes, input_fn):
        print("Aborted by user (runtime is deployed; re-run to finish the stack).")
        return 1
    runner(sam_argv, workdir, None, False)

    print(
        "\nDeployment complete.\n"
        f"  Upload documents to s3://{cfg.input_bucket}/ "
        "(pdf/ for PDFs, html/ for HTML or a .zip of HTML+CSS+JS).\n"
        "  Results are written under the accessible/ prefix."
    )
    return 0
