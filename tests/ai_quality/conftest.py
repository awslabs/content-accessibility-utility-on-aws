# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 7 — AWS-backed AI quality test harness and gating.

These fixtures support the opt-in tier that makes REAL Bedrock calls to evaluate
the QUALITY of model output (not just that the plumbing works). Everything here
is gated so it never runs — or costs money — in the default test run:

- Every test in this package must be marked ``@pytest.mark.aws`` (and usually
  ``@pytest.mark.llm_judge``). The default pytest config runs ``-m "not aws"``.
- On top of the marker, collection is skipped unless ``RUN_AWS_TESTS=1`` is set
  AND AWS credentials resolve, so an accidental ``pytest -m aws`` without
  credentials skips cleanly with a clear reason instead of erroring.

Approximate cost: each judged case is one small generation call (Nova 2 Lite)
plus N judge calls (Sonnet). A full run is a few cents; keep corpora small.
"""

import os
from pathlib import Path

import pytest

# A judge model deliberately STRONGER than the Nova 2 Lite model the app uses to
# generate, so the judge is not grading its own family's output.
JUDGE_MODEL_ID = os.environ.get(
    "AI_QUALITY_JUDGE_MODEL", "us.anthropic.claude-sonnet-4-6"
)

# Number of independent judge calls per assertion; the aggregate (majority /
# mean) decides pass to dampen single-call judge noise.
JUDGE_VOTES = int(os.environ.get("AI_QUALITY_JUDGE_VOTES", "3"))


def _aws_enabled() -> bool:
    """Whether the AWS-backed tier should actually run."""
    if os.environ.get("RUN_AWS_TESTS") != "1":
        return False
    try:
        import boto3

        # Credentials must resolve; we don't make a call here.
        return boto3.Session().get_credentials() is not None
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    """
    Skip every test in this package unless the AWS tier is explicitly enabled.

    A module-level ``pytestmark`` in a conftest does NOT propagate to test
    modules, so the gate is enforced here at collection time. This guarantees
    that even ``pytest -m aws`` makes no real Bedrock calls without
    ``RUN_AWS_TESTS=1`` and resolvable credentials.
    """
    if _aws_enabled():
        return
    skip = pytest.mark.skip(
        reason="AI quality tier is opt-in: set RUN_AWS_TESTS=1 with AWS credentials"
    )
    here = Path(__file__).resolve().parent
    for item in items:
        # Use a proper path-containment check (not string startswith, which a
        # sibling dir sharing the prefix or a symlink mismatch could defeat and
        # leak real Bedrock calls).
        item_path = Path(str(item.fspath)).resolve()
        if here == item_path or here in item_path.parents:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def bedrock_client():
    """Real BedrockClient using the app's default (Nova 2 Lite) model."""
    from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
        BedrockClient,
    )

    return BedrockClient()


@pytest.fixture(scope="session")
def judge():
    """
    LLM-as-a-judge callable: judge(output, criteria, context=None) -> verdict.

    See tests/ai_quality/judge.py for the implementation and verdict shape.
    """
    from tests.ai_quality.judge import make_judge

    return make_judge(model_id=JUDGE_MODEL_ID, votes=JUDGE_VOTES)
