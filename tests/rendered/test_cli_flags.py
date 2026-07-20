# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Browser-free tests that the --rendered / --agent CLI flags map to options.

These parse real CLI args and capture the options dict handed to
``audit_html_accessibility`` (monkeypatched), so they exercise the flag wiring
without launching a browser or calling AWS.
"""

import content_accessibility_utility_on_aws.cli as cli


def _run_audit_capturing_options(monkeypatch, tmp_path, argv_flags):
    """Run the audit command with given flags; return the options dict passed."""
    html = tmp_path / "page.html"
    html.write_text("<html lang='en'><head><title>t</title></head><body></body></html>")
    captured = {}

    def fake_audit(html_path, options=None, output_path=None, **kwargs):
        captured["options"] = options or {}
        # Minimal shape the command handler reads back.
        return {"report": "ok", "issues": []}

    monkeypatch.setattr(cli, "audit_html_accessibility", fake_audit)

    parser = cli.create_parser()
    args = parser.parse_args(
        ["audit", "-i", str(html), "-o", str(tmp_path / "out.json"), *argv_flags]
    )
    rc = cli.run_audit_command(vars(args))
    assert rc == 0
    return captured["options"]


def test_no_flag_leaves_rendered_unset(monkeypatch, tmp_path):
    options = _run_audit_capturing_options(monkeypatch, tmp_path, [])
    assert "rendered" not in options
    assert "agent" not in options


def test_rendered_flag_sets_rendered_only(monkeypatch, tmp_path):
    options = _run_audit_capturing_options(monkeypatch, tmp_path, ["--rendered"])
    assert options.get("rendered") is True
    assert "agent" not in options


def test_agent_flag_implies_rendered(monkeypatch, tmp_path):
    options = _run_audit_capturing_options(monkeypatch, tmp_path, ["--agent"])
    assert options.get("rendered") is True
    assert options.get("agent") is True


def test_process_command_threads_rendered(monkeypatch, tmp_path):
    """The process command's audit step also honors --rendered."""
    captured = {}

    def fake_audit(html_path, options=None, output_path=None, **kwargs):
        captured["options"] = options or {}
        return {"report": "ok", "issues": []}

    # Stub conversion + remediation so process() reaches the audit step cheaply.
    monkeypatch.setattr(cli, "audit_html_accessibility", fake_audit)
    monkeypatch.setattr(
        cli,
        "convert_pdf_to_html",
        lambda **kw: {"html_path": str(tmp_path / "doc.html")},
    )
    (tmp_path / "doc.html").write_text(
        "<html lang='en'><head><title>t</title></head><body></body></html>"
    )
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    parser = cli.create_parser()
    args = parser.parse_args(
        [
            "process",
            "-i",
            str(pdf),
            "-o",
            str(tmp_path / "out"),
            "--skip-remediation",
            "--rendered",
        ]
    )
    cli.run_process_command(vars(args))
    assert captured["options"].get("rendered") is True
