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


# --- single-page agent gating ------------------------------------------------
# Interactive single-file HTML (dashboards, widgets) is the agent's core case;
# it must not be reachable only for multi-page bundles.

_OPTS = {"agent": True, "rendered": True, "max_agent_pages": 10}


class _Probe:
    """Stand-in browser probe context manager (no real browser)."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _stub_agent(monkeypatch, fixed_html):
    """Patch the agent stack at its source modules (pipeline imports them
    locally inside the function, so patching pipe.* would not intercept)."""
    import content_accessibility_utility_on_aws.agent.browser_probe as bp
    import content_accessibility_utility_on_aws.agent.agent as ag

    monkeypatch.setattr(bp, "make_browser_probe", lambda opts: _Probe())
    monkeypatch.setattr(ag, "run_agent", lambda probe, html, options: {"html": fixed_html})


def test_single_page_agent_skipped_when_disabled(tmp_path):
    page = tmp_path / "p.remediated.html"
    page.write_text("<html><body><button>Go</button></body></html>")
    audit = _audit(_issue("p.html", "4.1.2"))
    assert pipe._run_agent_on_single_page(
        str(page), {"agent": False, "rendered": False}, audit
    ) == 0


def test_single_page_agent_skipped_without_agent_relevant_issue(tmp_path):
    page = tmp_path / "p.remediated.html"
    page.write_text("<html><body><h3>x</h3></body></html>")
    # Only a static-only finding (heading) -> agent adds nothing -> skip.
    audit = _audit(_issue("p.html", "1.3.1"))
    assert pipe._run_agent_on_single_page(str(page), _OPTS, audit) == 0


def test_single_page_agent_runs_and_persists_change(tmp_path, monkeypatch):
    page = tmp_path / "p.remediated.html"
    page.write_text("<html><body><span onclick='x()'>Go</span></body></html>")
    audit = _audit(_issue("p.html", "4.1.2"))
    fixed = "<html><body><span role='button' aria-label='Go'>Go</span></body></html>"
    _stub_agent(monkeypatch, fixed)

    assert pipe._run_agent_on_single_page(str(page), _OPTS, audit) == 1
    assert page.read_text() == fixed


def test_single_page_agent_no_change_returns_zero(tmp_path, monkeypatch):
    page = tmp_path / "p.remediated.html"
    original = "<html><body><span onclick='x()'>Go</span></body></html>"
    page.write_text(original)
    audit = _audit(_issue("p.html", "4.1.2"))
    _stub_agent(monkeypatch, original)  # agent returns identical HTML -> no-op

    assert pipe._run_agent_on_single_page(str(page), _OPTS, audit) == 0
    assert page.read_text() == original


def test_has_agent_relevant_issue():
    assert pipe._has_agent_relevant_issue(_audit(_issue("p.html", "4.1.2"))) is True
    assert pipe._has_agent_relevant_issue(_audit(_issue("p.html", "1.3.1"))) is False
    assert pipe._has_agent_relevant_issue(
        _audit(_issue("p.html", "4.1.2", status="compliant"))
    ) is False


# --- asset inlining ----------------------------------------------------------
# The probe renders an HTML string (and the hosted browser is remote), so linked
# local CSS/JS must be inlined or computed-style / interactive issues in those
# assets are invisible. These are browser-free unit tests of that transform.

def test_inline_local_css_and_js(tmp_path):
    (tmp_path / "css").mkdir()
    (tmp_path / "js").mkdir()
    (tmp_path / "css" / "s.css").write_text("button{outline:none}")
    (tmp_path / "js" / "s.js").write_text("console.log('x')")
    html = (
        '<html><head><link rel="stylesheet" href="css/s.css"></head>'
        '<body><script src="js/s.js"></script></body></html>'
    )
    out = pipe._inline_local_assets(html, str(tmp_path))
    assert "outline:none" in out
    assert "console.log('x')" in out
    assert 'href="css/s.css"' not in out  # link replaced by <style>
    assert 'src="js/s.js"' not in out     # script replaced by inline <script>


def test_inline_leaves_absolute_urls_untouched(tmp_path):
    html = (
        '<html><head>'
        '<link rel="stylesheet" href="https://cdn.example.com/x.css">'
        '<link rel="stylesheet" href="//cdn.example.com/y.css">'
        '</head><body><script src="https://cdn.example.com/a.js"></script></body></html>'
    )
    out = pipe._inline_local_assets(html, str(tmp_path))
    assert "https://cdn.example.com/x.css" in out
    assert "//cdn.example.com/y.css" in out
    assert "https://cdn.example.com/a.js" in out


def test_inline_rejects_path_traversal(tmp_path):
    # A secret outside base_dir must never be inlined via ../ traversal.
    secret = tmp_path / "secret.css"
    secret.write_text("SECRET{color:red}")
    base = tmp_path / "site"
    base.mkdir()
    html = '<html><head><link rel="stylesheet" href="../secret.css"></head><body></body></html>'
    out = pipe._inline_local_assets(html, str(base))
    assert "SECRET" not in out
    assert 'href="../secret.css"' in out  # left as-is, not inlined


def test_inline_noop_when_nothing_to_inline(tmp_path):
    html = "<html><body><p>hi</p></body></html>"
    assert pipe._inline_local_assets(html, str(tmp_path)) == html


def test_inline_skips_missing_asset(tmp_path):
    html = '<html><head><link rel="stylesheet" href="css/missing.css"></head><body></body></html>'
    out = pipe._inline_local_assets(html, str(tmp_path))
    assert out == html  # unresolved reference left untouched


def test_inline_skips_oversized_asset(tmp_path, monkeypatch):
    (tmp_path / "big.css").write_text("a{}")
    monkeypatch.setattr(pipe, "_MAX_INLINE_ASSET_BYTES", 1)  # force "too big"
    html = '<html><head><link rel="stylesheet" href="big.css"></head><body></body></html>'
    out = pipe._inline_local_assets(html, str(tmp_path))
    assert 'href="big.css"' in out  # not inlined
