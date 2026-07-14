# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 8 — LLM-as-a-judge framework.

Provides a ``judge(output, criteria, context)`` callable that scores generated
text against an explicit rubric using a strong model. Reliability measures:

- Structured output via the Converse API's forced tool use, so the score/verdict
  parse deterministically (no brittle text scraping).
- N independent votes decided by BOTH a mean-score threshold AND a majority of
  per-vote pass verdicts, so a single off judgment does not flip the result and
  a split panel does not pass on a lucky high score alone.
- Votes are sampled at ``temperature > 0`` so the N calls are genuinely
  independent draws (at ``temperature=0`` identical prompts would return
  identical scores, making extra votes pointless).
- Scores are clamped to the 1-5 rubric range and malformed judgments are dropped
  rather than crashing or skewing the mean.
- On failure the aggregated verdict carries each vote's rationale, surfaced in
  the test's assertion message so a red test explains *why* the output was poor.
"""

from dataclasses import dataclass
from typing import List, Optional

import boto3

from content_accessibility_utility_on_aws.remediate.services.bedrock_client import (
    BEDROCK_BOTO_CONFIG,
)

# Minimum mean score (1-5) required to pass, unless overridden. 4.0 keeps the
# gate above the rubric's "merely adequate" midpoint (3).
DEFAULT_PASS_THRESHOLD = 4.0

# Sampling temperature for judge votes — nonzero so the N votes are independent
# draws rather than identical deterministic responses.
JUDGE_TEMPERATURE = 0.7

# Forced-tool schema the judge must fill in.
_SCORE_TOOL = {
    "toolSpec": {
        "name": "record_score",
        "description": "Record the quality score for the candidate output.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "score": {
                        "type": "integer",
                        "description": "Quality score from 1 (poor) to 5 (excellent).",
                    },
                    "passed": {
                        "type": "boolean",
                        "description": "Whether the output meets the criteria.",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Brief justification for the score.",
                    },
                },
                "required": ["score", "passed", "rationale"],
            }
        },
    }
}


@dataclass
class Verdict:
    """Aggregated judging result across votes."""

    passed: bool
    mean_score: float
    scores: List[int]
    vote_passes: List[bool]
    rationales: List[str]

    def explain(self) -> str:
        lines = [
            f"passed={self.passed} mean_score={self.mean_score:.2f} "
            f"scores={self.scores} vote_passes={self.vote_passes}"
        ]
        for i, r in enumerate(self.rationales, 1):
            lines.append(f"  vote {i}: {r}")
        return "\n".join(lines)


def _clamp_score(raw) -> Optional[int]:
    """Coerce a model-reported score to an int in 1-5, or None if unusable."""
    try:
        score = int(raw)
    except (TypeError, ValueError):
        return None
    if score < 1 or score > 5:
        return None
    return score


def make_judge(
    model_id: str,
    votes: int = 3,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
):
    """
    Build a judge callable bound to a model.

    Args:
        model_id: The (strong) judge model id.
        votes: Number of independent judge calls per evaluation.
        pass_threshold: Minimum mean score (1-5) required to pass.

    Returns:
        judge(output, criteria, context=None) -> Verdict
    """
    client = boto3.client("bedrock-runtime", config=BEDROCK_BOTO_CONFIG)

    def _one_vote(output: str, criteria: str, context: Optional[str]) -> Optional[dict]:
        context_block = f"\n\nContext the output should fit:\n{context}" if context else ""
        prompt = (
            "You are a strict web-accessibility quality judge. Score the candidate "
            "output from 1 (poor) to 5 (excellent) against the criteria, and decide "
            f"whether it passes.{context_block}\n\n"
            f"Criteria:\n{criteria}\n\n"
            f"Candidate output:\n{output!r}"
        )
        resp = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            toolConfig={
                "tools": [_SCORE_TOOL],
                "toolChoice": {"tool": {"name": "record_score"}},
            },
            inferenceConfig={"maxTokens": 500, "temperature": JUDGE_TEMPERATURE},
        )
        for block in resp["output"]["message"]["content"]:
            if "toolUse" in block:
                return block["toolUse"]["input"]
        return None

    def judge(output: str, criteria: str, context: Optional[str] = None) -> Verdict:
        scores: List[int] = []
        vote_passes: List[bool] = []
        rationales: List[str] = []
        for _ in range(votes):
            result = _one_vote(output, criteria, context)
            if not result:
                continue  # drop a malformed judgment rather than crashing
            score = _clamp_score(result.get("score"))
            if score is None:
                continue  # out-of-range / non-numeric score is unusable
            scores.append(score)
            vote_passes.append(bool(result.get("passed")))
            rationales.append(str(result.get("rationale", "")))

        if not scores:
            raise AssertionError("Judge returned no usable scores across all votes")

        mean_score = sum(scores) / len(scores)
        # Pass requires BOTH: mean score at/above threshold AND a majority of
        # votes voting pass. Either signal failing fails the verdict, so a lucky
        # high outlier can't carry a split panel and vice versa.
        mean_ok = mean_score >= pass_threshold
        majority_ok = sum(vote_passes) * 2 > len(vote_passes)
        return Verdict(
            passed=mean_ok and majority_ok,
            mean_score=mean_score,
            scores=scores,
            vote_passes=vote_passes,
            rationales=rationales,
        )

    return judge
