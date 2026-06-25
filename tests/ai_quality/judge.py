# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Phase 8 — LLM-as-a-judge framework.

Provides a ``judge(output, criteria, context)`` callable that scores generated
text against an explicit rubric using a strong model. Reliability measures:

- Structured output via the Converse API's forced tool use, so the score/verdict
  parse deterministically (no brittle text scraping).
- ``temperature=0`` for repeatable judging.
- N independent votes aggregated by mean score + majority pass, so a single
  off judgment does not flip the result.
- On failure the aggregated verdict carries each vote's rationale, surfaced in
  the test's assertion message so a red test explains *why* the output was poor.
"""

from dataclasses import dataclass
from typing import List, Optional

import boto3
from botocore.config import Config

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
    rationales: List[str]

    def explain(self) -> str:
        lines = [f"mean_score={self.mean_score:.2f} scores={self.scores}"]
        for i, r in enumerate(self.rationales, 1):
            lines.append(f"  vote {i}: {r}")
        return "\n".join(lines)


def make_judge(model_id: str, votes: int = 3, pass_threshold: float = 3.0):
    """
    Build a judge callable bound to a model.

    Args:
        model_id: The (strong) judge model id.
        votes: Number of independent judge calls per evaluation.
        pass_threshold: Minimum mean score (1-5) required to pass.

    Returns:
        judge(output, criteria, context=None) -> Verdict
    """
    client = boto3.client(
        "bedrock-runtime",
        config=Config(retries={"max_attempts": 5, "mode": "adaptive"}, read_timeout=60),
    )

    def _one_vote(output: str, criteria: str, context: Optional[str]) -> dict:
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
            inferenceConfig={"maxTokens": 500, "temperature": 0},
        )
        for block in resp["output"]["message"]["content"]:
            if "toolUse" in block:
                return block["toolUse"]["input"]
        raise AssertionError("Judge did not return a structured score")

    def judge(output: str, criteria: str, context: Optional[str] = None) -> Verdict:
        scores: List[int] = []
        rationales: List[str] = []
        # Vary the prompt slightly per vote so identical-cache effects don't make
        # the votes perfectly correlated.
        for i in range(votes):
            tagged_criteria = f"{criteria}\n(evaluation pass {i + 1})"
            result = _one_vote(output, tagged_criteria, context)
            scores.append(int(result["score"]))
            rationales.append(result["rationale"])

        mean_score = sum(scores) / len(scores)
        passed = mean_score >= pass_threshold
        return Verdict(
            passed=passed, mean_score=mean_score, scores=scores, rationales=rationales
        )

    return judge
