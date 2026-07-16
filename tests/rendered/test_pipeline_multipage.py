# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser-free tests for the managed-pipeline core (agent.pipeline).

Covers the two behaviors that only surfaced on a real large document:
  - idempotency guard (AgentCore retries must not reprocess a COMPLETE job),
  - bounded candidate-page selection for the per-page agent on multi-page docs.
No AWS or browser needed — the S3/DDB touchpoints are monkeypatched.
"""

import os

import content_accessibility_utility_on_aws.agent.pipeline as pipe


def test_idempotency_skips_already_complete_job(monkeypatch):
    monkeypatch.setattr(
        pipe, "get_job_status",
        lambda job_id: {"status": pipe.STATUS_COMPLETED, "stage": pipe.STAGE_COMPLETE},
    )
    # If it did NOT skip, it would try to create a job record / touch S3.
    called = {"created": False}
    monkeypatch.setattr(pipe, "create_job_record", lambda *a, **k: called.__setitem__("created", True))

    result = pipe.run_pipeline({
        "input_bucket": "b", "input_key": "html/doc.html", "job_id": "j1",
    })
    assert result["status"] == "skipped"
    assert called["created"] is False


def test_force_bypasses_idempotency(monkeypatch):
    monkeypatch.setattr(
        pipe, "get_job_status",
        lambda job_id: {"status": pipe.STATUS_COMPLETED, "stage": pipe.STAGE_COMPLETE},
    )
    # With force, it proceeds past the guard (and then fails fast on unknown mode
    # only if we let it; here we stub the stages to prove it did NOT skip).
    monkeypatch.setattr(pipe, "create_job_record", lambda *a, **k: None)
    monkeypatch.setattr(pipe, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(pipe, "_run_audit", lambda *a, **k: {"status": "completed"})

    result = pipe.run_pipeline({
        "input_bucket": "b", "input_key": "html/doc.html", "job_id": "j1",
        "mode": "audit", "force": True,
    })
    assert result["status"] == "completed"


def test_missing_record_does_not_skip(monkeypatch):
    def _raise(job_id):
        raise RuntimeError("no such item")
    monkeypatch.setattr(pipe, "get_job_status", _raise)
    monkeypatch.setattr(pipe, "create_job_record", lambda *a, **k: None)
    monkeypatch.setattr(pipe, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(pipe, "_run_audit", lambda *a, **k: {"status": "completed"})
    result = pipe.run_pipeline({
        "input_bucket": "b", "input_key": "html/doc.html", "mode": "audit",
    })
    assert result["status"] == "completed"  # proceeded despite no record


def _audit(*issues):
    """Minimal audit-result shape with the given issues."""
    return {"issues": list(issues)}


def _issue(file_name, wcag, status="needs_remediation"):
    return {
        "wcag_criterion": wcag,
        "remediation_status": status,
        "file_name": file_name,
        "location": {"file_name": file_name},
    }


def test_candidate_pages_selects_only_agent_relevant_findings(tmp_path):
    # 3 pages exist; audit flags page-1 with contrast (agent-relevant) and page-0
    # with a heading issue (static-only). page-2 has no findings.
    for i in range(3):
        (tmp_path / f"page-{i}.html").write_text("<html><body>x</body></html>")
    audit = _audit(
        _issue("page-0.html", "1.3.1"),          # structural: NOT agent-relevant
        _issue("page-1.html", "1.4.3"),          # contrast: agent-relevant
    )
    picks = pipe._candidate_pages(str(tmp_path), cap=25, audit_result=audit)
    bases = sorted(os.path.basename(p) for p in picks)
    assert bases == ["page-1.html"]  # only the contrast page


def test_candidate_pages_empty_when_no_agent_relevant_issues(tmp_path):
    # This is the Unilever case: many issues, none agent-relevant → agent skipped.
    (tmp_path / "page-0.html").write_text("<html><body>x</body></html>")
    audit = _audit(
        _issue("page-0.html", "1.3.1"),
        _issue("page-0.html", "2.4.2"),
    )
    picks = pipe._candidate_pages(str(tmp_path), cap=25, audit_result=audit)
    assert picks == []


def test_candidate_pages_ignores_compliant_findings(tmp_path):
    (tmp_path / "page-0.html").write_text("<html><body>x</body></html>")
    audit = _audit(_issue("page-0.html", "2.4.7", status="compliant"))
    assert pipe._candidate_pages(str(tmp_path), cap=25, audit_result=audit) == []


def test_candidate_pages_respects_cap(tmp_path):
    for i in range(5):
        (tmp_path / f"page-{i}.html").write_text("<html><body>x</body></html>")
    audit = _audit(*[_issue(f"page-{i}.html", "2.4.7") for i in range(5)])
    picks = pipe._candidate_pages(str(tmp_path), cap=2, audit_result=audit)
    assert len(picks) == 2


def test_candidate_pages_dom_fallback_without_audit(tmp_path):
    # No audit result → DOM heuristic (interactive/image pages).
    (tmp_path / "page-0.html").write_text("<html><body><p>text</p></body></html>")
    (tmp_path / "page-1.html").write_text("<html><body><button>Go</button></body></html>")
    picks = pipe._candidate_pages(str(tmp_path), cap=25, audit_result=None)
    assert [os.path.basename(p) for p in picks] == ["page-1.html"]


def test_agent_skipped_when_disabled(tmp_path):
    (tmp_path / "p.html").write_text("<html><body><button>Go</button></body></html>")
    # agent + rendered both off -> no agent pass, returns 0.
    n = pipe._run_agent_on_candidate_pages(str(tmp_path), {"agent": False, "rendered": False})
    assert n == 0
