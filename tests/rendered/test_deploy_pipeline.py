# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Offline tests for the interactive deploy orchestrator (deploy-pipeline).

No AWS, no agentcore/sam, no real subprocess: the runner, scaffold, prompts, and
prerequisite check are all injected so the orchestration logic (ARN capture,
step ordering, confirmations, dry-run, BDA-optional) is exercised deterministically.
"""

import content_accessibility_utility_on_aws.deploy as deploy


# --- pure helpers ------------------------------------------------------------

def test_parse_runtime_arn_takes_last_match():
    out = (
        "Agent created/updated: "
        "arn:aws:bedrock-agentcore:us-east-1:111122223333:runtime/a11y_pipeline-AAA\n"
        "Deployment completed successfully - Agent: "
        "arn:aws:bedrock-agentcore:us-east-1:111122223333:runtime/a11y_pipeline-ZZZ"
    )
    assert deploy.parse_runtime_arn(out).endswith("a11y_pipeline-ZZZ")


def test_parse_runtime_arn_none_when_absent():
    assert deploy.parse_runtime_arn("no arn in here") is None
    assert deploy.parse_runtime_arn("") is None


def test_read_arn_from_yaml(tmp_path):
    cfg = tmp_path / ".bedrock_agentcore.yaml"
    cfg.write_text(
        "agents:\n  a11y:\n    bedrock_agentcore:\n"
        "      agent_arn: arn:aws:bedrock-agentcore:us-east-1:111122223333:runtime/x-Y\n"
    )
    assert deploy.read_arn_from_yaml(str(cfg)).endswith("runtime/x-Y")


def test_read_arn_from_yaml_missing_file(tmp_path):
    assert deploy.read_arn_from_yaml(str(tmp_path / "nope.yaml")) is None


def test_build_plan_includes_bda_env_only_when_set():
    with_bda = deploy.build_plan(
        deploy.DeployConfig(region="us-east-1", bda_bucket="b", bda_project_arn="arn:x")
    )
    launch = [s for s in with_bda if s.argv[:2] == ["agentcore", "launch"]][0]
    assert "--env" in launch.argv and "BDA_S3_BUCKET=b" in launch.argv

    without = deploy.build_plan(deploy.DeployConfig(region="us-east-1"))
    launch2 = [s for s in without if s.argv[:2] == ["agentcore", "launch"]][0]
    assert "--env" not in launch2.argv


# --- orchestration (injected runner/scaffold) --------------------------------

class _Recorder:
    """Records commands and returns canned output for `agentcore launch`."""

    def __init__(self, launch_arn):
        self.calls = []
        self._launch_arn = launch_arn

    def __call__(self, argv, cwd, extra_env=None):
        self.calls.append(argv)
        if argv[:2] == ["agentcore", "launch"]:
            return f"Deployment completed successfully - Agent: {self._launch_arn}"
        return ""


def _cfg(**kw):
    base = dict(directory="a11y-x", region="us-east-1", input_bucket="bkt")
    base.update(kw)
    return deploy.DeployConfig(**base)


def test_dry_run_runs_nothing(capsys):
    calls = []
    rc = deploy.run_deploy(
        _cfg(bda_bucket="b", bda_project_arn="arn:x"),
        scaffold=lambda d, f: calls.append(("scaffold", d)),
        dry_run=True,
        runner=lambda *a, **k: calls.append("RAN") or "",
    )
    assert rc == 0
    assert "RAN" not in calls  # nothing executed
    assert "Deployment plan:" in capsys.readouterr().out


def test_full_flow_captures_arn_and_deploys(monkeypatch):
    arn = "arn:aws:bedrock-agentcore:us-east-1:111122223333:runtime/a11y_pipeline-ZZZ"
    rec = _Recorder(arn)
    scaffolded = []
    # All prerequisites present.
    monkeypatch.setattr(deploy, "check_prerequisites", lambda *a, **k: [])

    rc = deploy.run_deploy(
        _cfg(bda_bucket="b", bda_project_arn="arn:proj"),
        scaffold=lambda d, f: scaffolded.append(d),
        assume_yes=True,
        runner=rec,
    )
    assert rc == 0
    assert scaffolded == ["a11y-x"]
    # Order: configure, launch, then sam deploy with the captured ARN.
    assert rec.calls[0][:2] == ["agentcore", "configure"]
    assert rec.calls[1][:2] == ["agentcore", "launch"]
    sam = rec.calls[2]
    assert sam[:2] == ["sam", "deploy"]
    assert f"AgentRuntimeArn={arn}" in sam
    assert "InputBucketName=bkt" in sam


def test_arn_falls_back_to_yaml(tmp_path, monkeypatch):
    # Launch output has no ARN; the toolkit yaml does.
    monkeypatch.setattr(deploy, "check_prerequisites", lambda *a, **k: [])
    workdir = tmp_path / "a11y-x"
    workdir.mkdir()
    arn = "arn:aws:bedrock-agentcore:us-east-1:111122223333:runtime/from-yaml"
    (workdir / ".bedrock_agentcore.yaml").write_text(f"      agent_arn: {arn}\n")

    class _NoArnRunner:
        def __init__(self):
            self.calls = []

        def __call__(self, argv, cwd, extra_env=None):
            self.calls.append(argv)
            return "launched, but no arn printed"

    rec = _NoArnRunner()
    rc = deploy.run_deploy(
        _cfg(directory=str(workdir)),
        scaffold=lambda d, f: None,
        assume_yes=True,
        runner=rec,
    )
    assert rc == 0
    sam = [c for c in rec.calls if c[:2] == ["sam", "deploy"]][0]
    assert f"AgentRuntimeArn={arn}" in sam


def test_missing_prerequisites_aborts(monkeypatch, capsys):
    monkeypatch.setattr(deploy, "check_prerequisites", lambda *a, **k: ["agentcore", "sam"])
    rc = deploy.run_deploy(
        _cfg(), scaffold=lambda d, f: None, assume_yes=True, runner=lambda *a, **k: ""
    )
    assert rc == 1
    assert "Missing required tool" in capsys.readouterr().out


def test_declining_confirmation_aborts_before_running(monkeypatch):
    monkeypatch.setattr(deploy, "check_prerequisites", lambda *a, **k: [])
    calls = []
    rc = deploy.run_deploy(
        _cfg(),
        scaffold=lambda d, f: None,
        assume_yes=False,
        input_fn=lambda prompt: "n",   # decline the first confirmation
        runner=lambda *a, **k: calls.append(a) or "",
    )
    assert rc == 1
    assert calls == []  # nothing ran


def test_prereq_check_detects_missing(monkeypatch):
    present = {"sam": "/usr/bin/sam"}
    missing = deploy.check_prerequisites(which=lambda t: present.get(t))
    assert "agentcore" in missing and "sam" not in missing


def test_prompt_fills_missing_and_requires_region_and_bucket(monkeypatch):
    # runtime_name defaults to a non-empty value, so it is NOT prompted; the
    # prompts asked, in order, are: directory, region, input bucket, BDA bucket.
    monkeypatch.delenv("AWS_REGION", raising=False)
    answers = iter(["mydir", "us-west-2", "mybucket", ""])
    cfg = deploy.prompt_for_config(
        deploy.DeployConfig(directory="", region="", input_bucket=""),
        input_fn=lambda p: next(answers),
    )
    assert cfg.directory == "mydir"
    assert cfg.region == "us-west-2"
    assert cfg.input_bucket == "mybucket"
    assert cfg.bda_bucket == ""  # skipped -> HTML/zip only
    assert cfg.runtime_name == deploy.DEFAULT_RUNTIME_NAME  # pre-filled, not prompted


def test_prompt_errors_without_region(monkeypatch):
    import pytest

    monkeypatch.delenv("AWS_REGION", raising=False)
    # directory, region (blank), input bucket, bda (blank) -> region empty -> error
    answers = iter(["d", "", "b", ""])
    with pytest.raises(deploy.DeployError):
        deploy.prompt_for_config(
            deploy.DeployConfig(directory="", region="", input_bucket=""),
            input_fn=lambda p: next(answers),
        )
