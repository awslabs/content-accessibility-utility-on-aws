# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for the `init-pipeline` scaffold command (browser-free, no AWS).

Verifies the bundled deployment assets are shipped in the package and written
out correctly, so users can deploy from a pip install alone.
"""

import os

import content_accessibility_utility_on_aws.cli as cli

EXPECTED = {
    "template.yaml",
    "agentcore_app.py",
    "requirements.txt",
    "README.md",
    os.path.join("trigger_lambda", "handler.py"),
}


def _run(tmp_path, *extra):
    parser = cli.create_parser()
    args = parser.parse_args(["init-pipeline", str(tmp_path), *extra])
    return cli.run_init_pipeline_command(vars(args))


def test_writes_all_deployment_files(tmp_path):
    out = tmp_path / "pipe"
    rc = _run(out)
    assert rc == 0
    for rel in EXPECTED:
        assert (out / rel).is_file(), f"missing {rel}"


def test_requirements_reference_published_agent_extra(tmp_path):
    out = tmp_path / "pipe"
    _run(out)
    reqs = (out / "requirements.txt").read_text()
    # Runtime installs the published package with the agent extra (no local wheel).
    assert "content-accessibility-utility-on-aws[agent]" in reqs
    assert ".whl" not in reqs


def test_template_is_a_cloudformation_sam_template(tmp_path):
    out = tmp_path / "pipe"
    _run(out)
    tpl = (out / "template.yaml").read_text()
    assert "AWS::Serverless" in tpl
    assert "AgentRuntimeArn" in tpl


def test_does_not_overwrite_without_force(tmp_path):
    out = tmp_path / "pipe"
    _run(out)
    (out / "template.yaml").write_text("CUSTOMIZED")
    _run(out)  # no --force
    assert (out / "template.yaml").read_text() == "CUSTOMIZED"


def test_force_overwrites(tmp_path):
    out = tmp_path / "pipe"
    _run(out)
    (out / "template.yaml").write_text("CUSTOMIZED")
    _run(out, "--force")
    assert (out / "template.yaml").read_text() != "CUSTOMIZED"
    assert "AWS::Serverless" in (out / "template.yaml").read_text()
